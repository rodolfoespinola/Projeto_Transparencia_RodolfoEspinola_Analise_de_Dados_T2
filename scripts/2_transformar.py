"""
2_transformar.py  -  FASE 2: Transformacao e Camada SILVER
----------------------------------------------------------
Pega os dados "sujos" da camada RAW (tudo texto) e preenche as tabelas SILVER
(ja criadas, com PK/FK, pelo 0_criar_banco.txt) com os dados limpos e tipados.

As etapas executadas:
  1. Esvazia as tabelas SILVER (para nao duplicar se rodar novamente).
  2. Copia da RAW para a SILVER, convertendo os tipos e calculando as
     colunas derivadas (valor_total, duracao_dias) na mesma consulta.

------------------------------------------------------------------------------
COMO CONVERTEMOS O TEXTO DA CAMADA RAW (esse padrao se repete no SQL abaixo):

  - Dinheiro: "1.234,50" (texto)  ->  1234.50 (numero DECIMAL)
      tira o ponto de milhar, troca a virgula por ponto e faz CAST:
      CAST(REPLACE(REPLACE(NULLIF(TRIM(coluna), ''), '.', ''), ',', '.') AS DECIMAL(10,2))

  - Data: "30/06/2025" (texto)  ->  2025-06-30 (tipo DATE)
      STR_TO_DATE(NULLIF(TRIM(coluna), ''), '%d/%m/%Y')

  Obs.: NULLIF(coluna, '') transforma um campo vazio em NULL (vazio no banco).
------------------------------------------------------------------------------
"""

import banco


# 1) Esvaziar as tabelas SILVER (idempotencia).
LIMPAR_SILVER = [
    "DELETE FROM silver_pagamento",
    "DELETE FROM silver_passagem",
    "DELETE FROM silver_trecho",
    "DELETE FROM silver_viagem",
]


# 2) Copiar RAW -> SILVER convertendo os tipos.
SQL_VIAGEM = """
INSERT INTO silver_viagem (
    id_viagem, num_proposta, situacao, viagem_urgente,
    cod_orgao_superior, nome_orgao_superior, nome_viajante, cargo,
    data_inicio, data_fim, destinos, motivo,
    valor_diarias, valor_passagens, valor_devolucao, valor_outros_gastos,
    valor_total, duracao_dias
)
SELECT
    id_viagem, num_proposta, situacao, viagem_urgente,
    cod_orgao_superior, nome_orgao_superior, nome_viajante, cargo,
    data_inicio, data_fim, destinos, motivo,
    valor_diarias, valor_passagens, valor_devolucao, valor_outros_gastos,
    (COALESCE(valor_diarias, 0) + COALESCE(valor_passagens, 0)
    + COALESCE(valor_outros_gastos, 0) - COALESCE(valor_devolucao, 0)) AS valor_total,
    DATEDIFF(data_fim, data_inicio) AS duracao_dias
FROM (
    SELECT
        id_viagem,
        NULLIF(TRIM(num_proposta), '')      AS num_proposta,
        NULLIF(TRIM(situacao), '')          AS situacao,
        NULLIF(TRIM(viagem_urgente), '')    AS viagem_urgente,
        NULLIF(TRIM(cod_orgao_superior), '') AS cod_orgao_superior,
        TRIM(nome_orgao_superior)           AS nome_orgao_superior,
        NULLIF(TRIM(nome_viajante), '')     AS nome_viajante,
        NULLIF(TRIM(cargo), '')             AS cargo,
        STR_TO_DATE(NULLIF(TRIM(data_inicio), ''), '%d/%m/%Y') AS data_inicio,
        STR_TO_DATE(NULLIF(TRIM(data_fim),    ''), '%d/%m/%Y') AS data_fim,
        NULLIF(TRIM(destinos), '')          AS destinos,
        NULLIF(TRIM(motivo), '')            AS motivo,
        CAST(REPLACE(REPLACE(NULLIF(TRIM(valor_diarias),      ''), '.', ''), ',', '.') AS DECIMAL(10,2)) AS valor_diarias,
        CAST(REPLACE(REPLACE(NULLIF(TRIM(valor_passagens),    ''), '.', ''), ',', '.') AS DECIMAL(10,2)) AS valor_passagens,
        CAST(REPLACE(REPLACE(NULLIF(TRIM(valor_devolucao),    ''), '.', ''), ',', '.') AS DECIMAL(10,2)) AS valor_devolucao,
        CAST(REPLACE(REPLACE(NULLIF(TRIM(valor_outros_gastos),''), '.', ''), ',', '.') AS DECIMAL(10,2)) AS valor_outros_gastos
    FROM raw_viagem
    WHERE NULLIF(TRIM(id_viagem), '') IS NOT NULL
      AND NULLIF(TRIM(nome_orgao_superior), '') IS NOT NULL
) viagem_tipagem
"""


SQL_PAGAMENTO = """
INSERT INTO silver_pagamento (
    id_viagem, num_proposta, nome_orgao_pagador, nome_ug_pagadora,
    tipo_pagamento, valor
)
SELECT
    id_viagem,
    NULLIF(TRIM(num_proposta), ''),
    NULLIF(TRIM(nome_orgao_pagador), ''),
    NULLIF(TRIM(nome_ug_pagadora), ''),
    TRIM(tipo_pagamento),
    CAST(REPLACE(REPLACE(NULLIF(TRIM(valor), ''), '.', ''), ',', '.') AS DECIMAL(10,2))
FROM raw_pagamento
WHERE id_viagem IN (SELECT id_viagem FROM silver_viagem)
  AND NULLIF(TRIM(tipo_pagamento), '') IS NOT NULL
"""

SQL_PASSAGEM = """
INSERT INTO silver_passagem (
    id_viagem, meio_transporte, pais_origem_ida, uf_origem_ida,
    cidade_origem_ida, pais_destino_ida, uf_destino_ida, cidade_destino_ida,
    valor_passagem, taxa_servico, data_emissao
)
SELECT
    id_viagem,
    NULLIF(TRIM(meio_transporte), ''),
    NULLIF(TRIM(pais_origem_ida), ''),
    NULLIF(TRIM(uf_origem_ida), ''),
    NULLIF(TRIM(cidade_origem_ida), ''),
    NULLIF(TRIM(pais_destino_ida), ''),
    NULLIF(TRIM(uf_destino_ida), ''),
    NULLIF(TRIM(cidade_destino_ida), ''),
    CAST(REPLACE(REPLACE(NULLIF(TRIM(valor_passagem), ''), '.', ''), ',', '.') AS DECIMAL(10,2)),
    CAST(REPLACE(REPLACE(NULLIF(TRIM(taxa_servico),   ''), '.', ''), ',', '.') AS DECIMAL(10,2)),
    STR_TO_DATE(NULLIF(TRIM(data_emissao), ''), '%d/%m/%Y')
FROM raw_passagem
WHERE id_viagem IN (SELECT id_viagem FROM silver_viagem)
"""

SQL_TRECHO = """
INSERT INTO silver_trecho (
    id_viagem, sequencia_trecho, origem_data, origem_uf, origem_cidade,
    destino_data, destino_uf, destino_cidade, meio_transporte, numero_diarias
)
SELECT
    id_viagem,
    CAST(NULLIF(TRIM(sequencia_trecho), '') AS UNSIGNED),
    STR_TO_DATE(NULLIF(TRIM(origem_data), ''), '%d/%m/%Y'),
    NULLIF(TRIM(origem_uf), ''),
    NULLIF(TRIM(origem_cidade), ''),
    STR_TO_DATE(NULLIF(TRIM(destino_data), ''), '%d/%m/%Y'),
    NULLIF(TRIM(destino_uf), ''),
    NULLIF(TRIM(destino_cidade), ''),
    NULLIF(TRIM(meio_transporte), ''),
    CAST(REPLACE(REPLACE(NULLIF(TRIM(numero_diarias), ''), '.', ''), ',', '.') AS DECIMAL(10,2))
FROM raw_trecho
WHERE id_viagem IN (SELECT id_viagem FROM silver_viagem)
"""


def main():
    print("=== FASE 2: TRANSFORMACAO + CAMADA SILVER ===")
    conexao = banco.conectar()
    try:
        print("[1/2] Esvaziando as tabelas SILVER...")
        for comando in LIMPAR_SILVER:
            banco.executar(conexao, comando)
 
        print("[2/2] Copiando, convertendo e calculando RAW -> SILVER...")
        banco.executar(conexao, SQL_VIAGEM)
        print("      silver_viagem    OK")
        banco.executar(conexao, SQL_PAGAMENTO)
        print("      silver_pagamento OK")
        banco.executar(conexao, SQL_PASSAGEM)
        print("      silver_passagem  OK")
        banco.executar(conexao, SQL_TRECHO)
        print("      silver_trecho    OK")
 
        print("=== Camada SILVER concluida com sucesso! ===")
    except Exception as erro:
        print("[ERRO] Algo deu errado:", erro)
        raise
    finally:
        conexao.close()



if __name__ == "__main__":
    main()