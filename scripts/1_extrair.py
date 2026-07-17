import zipfile
import gdown
import pandas as pd
import config
import banco

# ---------------------------------------------------------------------------
# Passo 1 - Biaxar o arquivo .zip na pasta data/
# ---------------------------------------------------------------------------
def baixar_zip():
    """Baixa o .zip do Google Drive para a pasta data/, caso o arquivo já não esteja lá."""
    config.PASTA_DADOS.mkdir(exist_ok=True)
    destino = config.PASTA_DADOS / "viagens.zip"

    if destino.exists():
        print("[1/3] O arquivo já foi baixado antes - pulando o download.")
        return destino
    
    print("[1/3] Baixando o arquivo do Google Drive...")
    try:
        gdown.download(id=config.DRIVE_FILE_ID, output=str(destino))
    except Exception as erro:
        raise RuntimeError(f"Falha ao baixar o .zip do Google Drive: {erro}")

    if not destino.exists():
        raise RuntimeError("O arquivo .zip não foi encontrado.")
    return destino

#---------------------------------------------------------------------------
# Passo 2 - Carregar um CSV dentro da sua tabela RAW
# ---------------------------------------------------------------------------

def carregar_csv(conexao, zip_aberto, nome_csv, tabela):
    """Le um CSV de dentro do zip e insere todas as linhas na tabela do MySQL.

    As colunas do CSV estao na MESMA ordem das colunas da tabela
    (definidas no 0_criar_banco.txt). Por isso conseguimos inserir "na ordem",
    sem precisar escrever o nome de cada coluna.
    """
    print("      Carregando", tabela, "...")

    # esvazia a tabela antes de carregar (assim, rodar de novo nao duplica dados)
    banco.executar(conexao, f"TRUNCATE TABLE {tabela}")
    total = 0
    with zip_aberto.open(nome_csv) as arquivo:
        # le o CSV em pedacos, para nao encher a memoria do PC em bases grandes
        pedacos = pd.read_csv(
            arquivo,
            sep=";",                     # colunas separadas por ponto-e-virgula
            encoding="latin-1",          # acentuacao dos arquivo do governo
            dtype=str,                   # tudo como texto (camada RAW)
            keep_default_na=False,       # campo vazio continua "" (nao vira "NaN")
            chunksize=config.TAMANHO_BLOCO,
        )
        for pedaco in pedacos:
            linhas = pedaco.values.tolist()
            # um "%s" para cada coluna do CSV
            marcadores = ", ".join(["%s"] * len(pedaco.columns))
            comando = f"INSERT INTO {tabela} VALUES ({marcadores})"
            banco.inserir_em_lote(conexao, comando, linhas)
            total += len(linhas)

    print("      ->", total, "linhas em", tabela)

# ---------------------------------------------------------------------------
# Programa principal
# ---------------------------------------------------------------------------
def main():
    print("=== FASE 1: EXTRACAO + CAMADA RAW ===")
    try:
        conexao = banco.conectar()

        caminho_zip = baixar_zip()
        print("[2/3] Abrindo o arquivo zip...")
        print("[3/3] Carregando as 4 tabelas RAW...")
        with zipfile.ZipFile(caminho_zip) as zip_aberto:
            for arquivo in config.ARQUIVOS.values():
                carregar_csv(conexao, zip_aberto, arquivo["csv"], arquivo["tabela_raw"])

        conexao.close()
        print("=== Camada RAW concluida com sucesso! ===")
    except Exception as erro:
        print("[ERRO] Algo deu errado:", erro)
        raise


if __name__ == "__main__":
    main()