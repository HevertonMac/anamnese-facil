# Casos Clínicos

Coloque aqui os arquivos `.docx` dos casos clínicos validados no formato `Caso_N.docx` (ex: `Caso_1.docx`, `Caso_2.docx`, ...).

Os arquivos **não são versionados** no Git (listados no `.gitignore`) pois podem conter dados médicos sensíveis.

Após adicionar os arquivos, execute a ingestão:

```bash
# Com Docker:
docker compose exec backend python -m scripts.ingest.ingest_cases --cases-dir /app/data/cases

# Localmente (com env ativo):
cd backend
python -m scripts.ingest.ingest_cases --cases-dir data/cases/
```
