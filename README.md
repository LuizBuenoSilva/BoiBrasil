# Cattle AI — Cadastro e Identificação de Gado em Tempo Real

Sistema de visão computacional para identificação individual de bovinos usando **YOLOv8** (detecção) + **EfficientNet-B0** (embeddings visuais) + **Claude claude-sonnet-4-6** (descrição automática via API).

## Funcionalidades

- **Detecção em tempo real** — YOLOv8n identifica vacas no frame usando a classe COCO 19
- **Identificação individual** — EfficientNet-B0 extrai vetores de features (1280-dim) comparados por cosine similarity
- **Cadastro interativo** — Pressione `R` para registrar um animal, com seleção por `Tab` entre múltiplos animais
- **Descrição automática** — Claude claude-sonnet-4-6 Vision analisa a imagem e gera descrição em terminologia pecuária
- **Banco de dados local** — SQLite armazena embeddings, fotos e descrições (sem dependência de servidor)
- **Fonte configurável** — Webcam, arquivo de vídeo MP4 ou stream RTSP

## Instalação

```bash
cd cattle-ai
pip install -r requirements.txt
```

### Configurar a API do Claude (opcional, mas recomendado)

```bash
# Linux/macOS
export ANTHROPIC_API_KEY=sk-ant-...

# Windows (PowerShell)
$env:ANTHROPIC_API_KEY = "sk-ant-..."

# Windows (CMD)
set ANTHROPIC_API_KEY=sk-ant-...
```

## Uso

### Iniciar com webcam padrão
```bash
python main.py run
```

### Iniciar com arquivo de vídeo
```bash
python main.py run --source /caminho/para/video.mp4
```

### Iniciar com câmera IP (RTSP)
```bash
python main.py run --source rtsp://192.168.1.100:554/stream
```

### Opções avançadas
```bash
# Modelo maior (mais preciso, mais lento)
python main.py run --model yolov8s.pt

# Ajustar thresholds
python main.py run --conf 0.5 --threshold 0.80

# Sem integração Claude (100% offline)
python main.py run --no-claude

# Banco de dados customizado
python main.py run --db meu_rebanho.db
```

### Listar todos os animais cadastrados
```bash
python main.py list
```

## Controles (janela OpenCV)

| Tecla | Ação |
|-------|------|
| `R` | Entrar no modo de registro |
| `Tab` | Selecionar próxima vaca detectada |
| `Enter` | Confirmar cadastro do animal selecionado |
| `L` | Listar todos os cadastrados no terminal |
| `Q` / `Esc` | Sair |

## Fluxo de Cadastro

1. Posicione a câmera com a vaca visível
2. Pressione `R` — o sistema entra em modo registro (overlay azul)
3. Use `Tab` se houver múltiplas vacas para selecionar o animal certo
4. Pressione `Enter` — o terminal solicitará o nome/ID do animal
5. Digite o nome e pressione Enter
6. Claude gera a descrição automaticamente (se configurado)
7. O animal aparece identificado (label verde) nos frames seguintes

## Arquitetura

```
Frame BGR
    │
    ▼
CattleDetector (YOLOv8n, class=19)
    │ list[Detection]
    ▼
CattleDetector.crop()
    │ crop BGR (por detecção)
    ▼
CattleEmbedder (EfficientNet-B0)
    │ ndarray float32 (1280,) L2-norm
    ▼
CattleIdentifier (cosine similarity)
    │ IdentityMatch(name, similarity, is_known)
    ▼
ui.draw_detection() + cv2.imshow()
```

### Banco de Identidades (in-memory)

O `CattleIdentifier` mantém um dicionário em memória carregado do SQLite na inicialização. Novos cadastros atualizam simultaneamente o banco SQLite e o dicionário, sem necessidade de reinicialização.

## Estrutura de Arquivos

```
cattle-ai/
├── main.py              # Entry point e loop de vídeo
├── detector.py          # Wrapper YOLOv8 com filtro de classe
├── embedder.py          # EfficientNet-B0 para embeddings
├── database.py          # CRUD SQLite
├── identifier.py        # Motor de cosine similarity
├── claude_analyzer.py   # Integração Claude Vision API
├── ui.py                # Desenho OpenCV (boxes, labels, HUD)
├── requirements.txt
├── cattle.db            # Criado automaticamente
└── photos/              # Crops salvos dos animais cadastrados
```

## Performance Esperada

| Configuração | FPS estimado |
|---|---|
| CPU (Intel i7), 1 vaca | 6–10 FPS |
| GPU (NVIDIA RTX), 1 vaca | 25–35 FPS |
| GPU (NVIDIA RTX), 3 vacas | 15–25 FPS |

Para uso em CPU, o sistema processa cada frame completo. Para melhor performance em CPU, use `--model yolov8n.pt` (padrão).

## Ajuste de Threshold

O threshold de cosine similarity (padrão `0.75`) controla a rigidez da identificação:

- `0.80–0.85` — Mais restrito: recomendado para rebanhos com animais de aparências muito semelhantes (ex: Angus preto)
- `0.75` — Padrão: bom equilíbrio geral
- `0.65–0.70` — Mais permissivo: recomendado para rebanhos com alta diversidade visual

```bash
python main.py run --threshold 0.70
```
