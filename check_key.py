import os

def check_key():
    print("Verificando chave da API Anthropic...")
    
    # 1. Verifica variável de ambiente
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        masked_key = f"{key[:15]}...{key[-4:]}" if len(key) > 20 else "Chave muito curta!"
        print(f"\n[ENCONTRADA] Variável de ambiente ANTHROPIC_API_KEY definida.")
        print(f"Valor: {masked_key}")
    else:
        print("\n[AUSENTE] Variável de ambiente ANTHROPIC_API_KEY não encontrada neste terminal.")

    # 2. Verifica arquivo .env local
    env_path = ".env"
    if os.path.exists(env_path):
        print(f"\n[ENCONTRADO] Arquivo .env encontrado em: {os.path.abspath(env_path)}")
        with open(env_path, "r") as f:
            found_in_file = False
            for line in f:
                line = line.strip()
                if line.startswith("ANTHROPIC_API_KEY"):
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        val = parts[1].strip().strip('"').strip("'")
                        masked_val = f"{val[:15]}...{val[-4:]}" if len(val) > 20 else "Chave curta"
                        print(f"Conteúdo do .env: ANTHROPIC_API_KEY = {masked_val}")
                        found_in_file = True
            if not found_in_file:
                print("Arquivo .env existe mas não contém ANTHROPIC_API_KEY.")
    else:
        print("\n[AUSENTE] Arquivo .env não encontrado no diretório atual.")

if __name__ == "__main__":
    check_key()
