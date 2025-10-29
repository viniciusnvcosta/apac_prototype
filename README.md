# Protótipo de Assistente Jurídico Inteligente – APAC/PE

Este repositório contém um protótipo de baixa fidelidade de uma plataforma
web para elaboração, revisão e exportação de peças jurídicas, conforme
proposto no desafio **Assistente Jurídico Inteligente – APAC/PE** do
programa Inova PE.  O objetivo é demonstrar, de forma simplificada, como
um editor online inspirado em serviços como o Google Docs pode integrar
funções de importação, edição, sumarização e exportação de documentos
jurídicos, bem como um esboço de mecanismo de autenticação e de catálogo
de leis e normativos relevantes.

## Funcionalidades Implementadas

- **Login Simples**: autenticação de demonstração com usuário e senha
  pré‑definidos.  Em uma aplicação real este módulo seria substituído
  por um serviço de gestão de identidades (IAM) com controle de acesso
  baseado em papéis.
- **Seleção do Tipo de Peça**: lista dos tipos de documentos
  contemplados no desafio.
- **Formulário de Dados**: campos para partes envolvidas, objeto e
  prazos, que poderão ser utilizados para preencher modelos
  padronizados.
- **Upload de Documentos**: suporte a arquivos `.txt` e `.docx` para
  iniciar ou complementar a edição de uma peça.
- **Editor de Texto**: área de edição onde o usuário pode escrever ou
  alterar o conteúdo do documento diretamente no navegador.
- **Resumo Automático**: função de sumarização extrativa que utiliza
  apenas as primeiras frases do texto como uma aproximação simples de
  um resumo.  Num sistema definitivo, esta funcionalidade seria
  fornecida por uma LLM treinada localmente e com isolamento de dados.
- **Exportação para DOCX**: geração de um arquivo `.docx` a partir do
  texto final.  Depende da biblioteca `python‑docx`.
- **Catálogo de Leis e Decretos**: listagem dos principais normativos
  que devem ser considerados, com base no documento do desafio.

## Instalando e Executando

1. Clone ou copie este diretório.  Instale as dependências listadas em
   `requirements.txt`:

   ```bash
   pip install -r requirements.txt
   ```

2. Execute a aplicação com o Streamlit:

   ```bash
   streamlit run app.py
   ```

3. Acesse o endereço indicado no console (por padrão, `http://localhost:8501`).
   Use as credenciais `admin` / `password` para entrar.

## Considerações de Privacidade e LGPD

O protótipo não envia dados a servidores externos.  Todo o processamento,
incluindo a sumarização, ocorre localmente no navegador e no backend
Python.  Entretanto, uma solução real deverá assegurar a conformidade
com a Lei Geral de Proteção de Dados (LGPD).  Isso implica em controles
robustos de acesso, criptografia de dados em repouso e em trânsito,
anonimização de informações sensíveis e transparência no tratamento de
dados.  Além disso, por questões de sigilo profissional,
qualquer modelo de linguagem utilizado deve ser executado em ambiente
isolado dentro da infraestrutura da APAC/PE, evitando o vazamento de
informações confidenciais.

## Próximos Passos (Evoluções Possíveis)

Este protótipo pode ser estendido de várias maneiras para se aproximar
da solução final desejada:

1. **Integração com bases jurídicas**: Conectar‑se a sistemas de
   jurisprudência (STJ, STF, TCE‑PE, TJPE) e bases de leis para
   fundamentação automatizada, conforme requerido no desafio.
2. **Modelos LaTeX**: Criar modelos LaTeX para cada tipo de documento
   e gerar saídas consistentes em formato PDF e DOCX a partir dos
   campos fornecidos pelo usuário.
3. **Summarização e geração de texto com LLMs**: Treinar e hospedar um
   modelo de linguagem de grande porte de forma isolada, aplicando
   técnicas de fine tuning a partir de peças produzidas pela APAC/PE.
4. **Controle de acesso avançado**: Implementar autenticação baseada
   em tokens (JWT/OAuth2) com diferentes níveis de permissão (por
   exemplo, consulta versus edição).
5. **Padronização de Linguagem**: Utilizar algoritmos de verificação
   estilística para garantir que o texto siga o Manual de Redação da
   Presidência da República, padronizando a linguagem conforme as
   preferências do cliente.

Este repositório é apenas o ponto de partida para um desenvolvimento
completo.
