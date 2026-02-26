"""
main.py — Cattle AI: Cadastro e identificação de gado em tempo real.

Subcomandos:
  run   — Inicia o loop de vídeo com detecção e identificação
  list  — Lista todos os animais cadastrados no banco de dados

Uso:
  python main.py run [--source 0] [--model yolov8n.pt] [--conf 0.4]
                     [--threshold 0.75] [--db cattle.db] [--no-claude]
  python main.py list [--db cattle.db]
"""

import argparse
import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from claude_analyzer import ClaudeAnalyzer
from database import CattleDatabase, PHOTOS_DIR
from detector import CattleDetector, Detection
from embedder import CattleEmbedder
from identifier import CattleIdentifier, IdentityMatch, UNKNOWN_LABEL
from ui import draw_detection, draw_hud, draw_registration_overlay


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cattle AI — Cadastro e identificação de gado em tempo real",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python main.py run                              # webcam padrão
  python main.py run --source 1                   # segunda webcam
  python main.py run --source video.mp4           # arquivo de vídeo
  python main.py run --source rtsp://ip/stream    # câmera IP
  python main.py run --no-claude                  # sem integração Claude
  python main.py run --threshold 0.70             # identificação mais permissiva
  python main.py list                             # listar todos os cadastrados
        """,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcomando: run
    run_p = subparsers.add_parser("run", help="Iniciar loop de vídeo")
    run_p.add_argument(
        "--source", default="0",
        help="Fonte de vídeo: índice da webcam (0,1,...), caminho do arquivo ou URL RTSP. Padrão: 0",
    )
    run_p.add_argument(
        "--model", default="yolov8n.pt",
        help="Modelo YOLOv8 (nome ou caminho). Padrão: yolov8n.pt",
    )
    run_p.add_argument(
        "--conf", type=float, default=0.40,
        help="Threshold de confiança da detecção. Padrão: 0.40",
    )
    run_p.add_argument(
        "--threshold", type=float, default=0.75,
        help="Threshold de cosine similarity para identificação. Padrão: 0.75",
    )
    run_p.add_argument(
        "--db", default="cattle.db",
        help="Caminho do banco SQLite. Padrão: cattle.db",
    )
    run_p.add_argument(
        "--no-claude", action="store_true",
        help="Desabilitar geração de descrição via Claude API",
    )

    # Subcomando: list
    list_p = subparsers.add_parser("list", help="Listar todos os animais cadastrados")
    list_p.add_argument("--db", default="cattle.db")

    return parser.parse_args()


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------

class FPSCounter:
    """Contador de FPS com média móvel sobre os últimos N frames."""

    def __init__(self, window: int = 30):
        self._times: deque[float] = deque(maxlen=window)

    def tick(self) -> float:
        self._times.append(time.perf_counter())
        if len(self._times) < 2:
            return 0.0
        elapsed = self._times[-1] - self._times[0]
        return (len(self._times) - 1) / elapsed if elapsed > 0 else 0.0


def open_source(source: str) -> cv2.VideoCapture:
    """
    Abre a fonte de vídeo. Aceita índice int (webcam), caminho de arquivo ou URL RTSP.
    Lança RuntimeError se a fonte não puder ser aberta.
    """
    cap = cv2.VideoCapture(int(source) if source.isdigit() else source)
    if not cap.isOpened():
        raise RuntimeError(f"Não foi possível abrir a fonte de vídeo: {source!r}")
    # Minimiza latência de buffer (útil para streams RTSP)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap


def save_crop(crop_bgr: np.ndarray, name: str) -> str:
    """Salva crop na pasta photos/ e retorna o caminho relativo."""
    PHOTOS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    filename = f"{safe_name}_{timestamp}.jpg"
    path = PHOTOS_DIR / filename
    cv2.imwrite(str(path), crop_bgr)
    return str(path)


# ---------------------------------------------------------------------------
# Fluxo de cadastro
# ---------------------------------------------------------------------------

def run_registration(
    frame: np.ndarray,
    target_det: Detection,
    detector: CattleDetector,
    embedder: CattleEmbedder,
    identifier: CattleIdentifier,
    db: CattleDatabase,
    analyzer: ClaudeAnalyzer | None,
) -> bool:
    """
    Fluxo bloqueante de cadastro de um novo animal.

    1. Solicita nome/ID no terminal
    2. Extrai embedding do crop
    3. Chama Claude para descrição (se disponível)
    4. Salva foto e insere no banco de dados
    5. Atualiza o banco in-memory do identificador

    Retorna True em caso de sucesso, False se cancelado ou nome duplicado.
    """
    print("\n" + "=" * 60)
    print("[CADASTRO] Digite o nome/ID do animal (vazio para cancelar):")
    print("  > ", end="", flush=True)

    try:
        name = input().strip()
    except EOFError:
        name = ""

    if not name:
        print("[CADASTRO] Cancelado.")
        return False

    if db.exists(name):
        print(f"[CADASTRO] '{name}' já está cadastrado. Use um nome diferente.")
        return False

    # Extrai crop e embedding
    crop = detector.crop(frame, target_det, padding=15)
    if crop.size == 0:
        print("[CADASTRO] Crop inválido — bounding box fora dos limites.")
        return False

    if min(crop.shape[:2]) < 32:
        print("[CADASTRO] Detecção muito pequena para cadastro confiável.")
        return False

    print("[CADASTRO] Extraindo embedding...")
    embedding = embedder.extract_from_bgr(crop)

    # Descrição via Claude
    description = ""
    if analyzer is not None and analyzer.available:
        print("[CADASTRO] Gerando descrição com Claude...")
        description = analyzer.analyze(crop)
        if description:
            print(f"[CADASTRO] Descrição: {description}")
        else:
            print("[CADASTRO] Descrição não disponível (erro ou API não configurada).")
    elif analyzer is None or not analyzer.available:
        print("[CADASTRO] Claude não configurado — cadastrando sem descrição.")

    # Salva foto e persiste no banco
    photo_path = save_crop(crop, name)
    row_id = db.register(name, embedding, description, photo_path)
    identifier.add(name, embedding, description)

    print(f"[CADASTRO] '{name}' cadastrado com sucesso! (id={row_id})")
    print(f"[CADASTRO] Foto salva em: {photo_path}")
    print("=" * 60 + "\n")
    return True


# ---------------------------------------------------------------------------
# Listagem
# ---------------------------------------------------------------------------

def list_cattle(db_path: str) -> None:
    """Exibe tabela de todos os animais cadastrados no terminal."""
    db = CattleDatabase(db_path)
    records = db.list_all()

    if not records:
        print("\nNenhum animal cadastrado ainda.")
        print("Execute 'python main.py run' e pressione R para cadastrar.\n")
        return

    print(f"\n{'ID':<5} {'Nome':<22} {'Cadastrado em':<22} {'Foto':<35} Descrição")
    print("-" * 120)
    for r in records:
        desc_preview = (r["description"] or "—")[:45]
        photo = (r["photo_path"] or "—")[:33]
        print(
            f"{r['id']:<5} {r['name']:<22} {r['registered_at']:<22} "
            f"{photo:<35} {desc_preview}"
        )
    print(f"\nTotal: {len(records)} animal(is) cadastrado(s)\n")


# ---------------------------------------------------------------------------
# Loop principal
# ---------------------------------------------------------------------------

def run(args: argparse.Namespace) -> None:
    """Inicializa todos os módulos e executa o loop de vídeo em tempo real."""

    print("\n" + "=" * 60)
    print("  Cattle AI — Identificação de Gado em Tempo Real")
    print("=" * 60)

    print("[Init] Carregando modelo YOLOv8...")
    detector = CattleDetector(
        model_path=args.model,
        conf_threshold=args.conf,
    )

    print("[Init] Carregando EfficientNet-B0...")
    embedder = CattleEmbedder()
    print(f"[Init] Embedder no device: {embedder.device}")

    print("[Init] Conectando ao banco de dados...")
    db = CattleDatabase(args.db)

    print("[Init] Carregando animais cadastrados...")
    identifier = CattleIdentifier(threshold=args.threshold)
    identifier.load_from_db(db.load_all())
    print(f"[Init] {identifier.registered_count} animal(is) no banco de identidades.")

    analyzer: ClaudeAnalyzer | None = None
    if not args.no_claude:
        analyzer = ClaudeAnalyzer()
        if analyzer.available:
            print("[Init] Claude API configurada e pronta.")
        else:
            print(
                "[Init] ANTHROPIC_API_KEY não encontrada — descrições desabilitadas.\n"
                "       Configure a variável de ambiente para habilitar."
            )
    else:
        print("[Init] Integração Claude desabilitada (--no-claude).")

    print(f"[Init] Abrindo fonte de vídeo: {args.source!r}")
    cap = open_source(args.source)

    cv2.namedWindow("Cattle AI", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Cattle AI", 1280, 720)

    fps_counter = FPSCounter()
    registration_mode = False
    target_det_idx = 0
    last_detections: list[Detection] = []
    last_matches: list[IdentityMatch] = []
    freeze_frame: np.ndarray | None = None  # Frame congelado para o cadastro

    print("\n[Executando] Controles:")
    print("  R      — Entrar no modo de registro")
    print("  Tab    — Selecionar próxima vaca detectada")
    print("  Enter  — Confirmar cadastro do animal selecionado")
    print("  L      — Listar todos no terminal")
    print("  Q/Esc  — Sair\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[Loop] Fim do stream ou erro de leitura.")
            break

        # Detecção + identificação
        detections = detector.detect(frame)
        matches: list[IdentityMatch] = []
        for det in detections:
            crop = detector.crop(frame, det, padding=10)
            if crop.size == 0 or min(crop.shape[:2]) < 16:
                matches.append(
                    IdentityMatch(name=UNKNOWN_LABEL, similarity=0.0, is_known=False)
                )
                continue
            emb = embedder.extract_from_bgr(crop)
            matches.append(identifier.identify(emb))

        # Guarda para uso no cadastro
        last_detections = detections
        last_matches = matches

        # Ajusta índice de seleção
        if detections and target_det_idx >= len(detections):
            target_det_idx = len(detections) - 1

        # Renderização
        display = frame.copy()
        for i, (det, match) in enumerate(zip(detections, matches)):
            is_target = registration_mode and (i == target_det_idx)
            if is_target:
                draw_registration_overlay(display, det)
            draw_detection(display, det, match, is_registration_target=is_target)

        fps = fps_counter.tick()
        draw_hud(
            display,
            fps=fps,
            registered_count=identifier.registered_count,
            registration_mode=registration_mode,
            target_index=target_det_idx,
            total_detections=len(detections),
        )

        cv2.imshow("Cattle AI", display)

        # Tratamento de teclas
        key = cv2.waitKey(1) & 0xFF

        if key in (ord("q"), ord("Q"), 27):  # Q ou Esc
            break

        elif key in (ord("r"), ord("R")):
            if not detections:
                print("[Tecla] Nenhuma vaca detectada — impossível cadastrar.")
            else:
                registration_mode = True
                target_det_idx = 0
                freeze_frame = frame.copy()
                print(
                    f"[Tecla] Modo registro ativado. "
                    f"{len(detections)} vaca(s) detectada(s). "
                    "Pressione Tab para selecionar, Enter para confirmar."
                )

        elif key == 9:  # Tab — cicla entre detecções
            if detections:
                target_det_idx = (target_det_idx + 1) % len(detections)
                print(
                    f"[Tecla] Animal {target_det_idx + 1}/{len(detections)} selecionado."
                )

        elif key == 13:  # Enter — confirma cadastro
            if registration_mode and last_detections and freeze_frame is not None:
                safe_idx = min(target_det_idx, len(last_detections) - 1)
                target_det = last_detections[safe_idx]
                success = run_registration(
                    freeze_frame,
                    target_det,
                    detector,
                    embedder,
                    identifier,
                    db,
                    analyzer,
                )
                registration_mode = False
                freeze_frame = None
            elif not registration_mode:
                print("[Tecla] Pressione R primeiro para entrar no modo registro.")

        elif key == 27 and registration_mode:  # Esc cancela registro
            registration_mode = False
            freeze_frame = None
            print("[Tecla] Registro cancelado.")

        elif key in (ord("l"), ord("L")):
            list_cattle(args.db)

    cap.release()
    cv2.destroyAllWindows()
    print("\n[Encerrado] Cattle AI finalizado.")


# ---------------------------------------------------------------------------
# Entrada
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    if args.command == "list":
        list_cattle(args.db)
    elif args.command == "run":
        try:
            run(args)
        except RuntimeError as e:
            print(f"\n[Erro] {e}")
            sys.exit(1)
        except KeyboardInterrupt:
            print("\n[Interrompido] Encerrando...")
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
