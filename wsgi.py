"""Ponto de entrada WSGI para publicação no PythonAnywhere."""

# Lê a biblioteca padrão que permite descobrir caminhos do sistema.
import os
# Lê a biblioteca padrão que permite ajustar os caminhos de importação do Python.
import sys


# Descobre o caminho absoluto da pasta que contém este arquivo.
project_dir = os.path.dirname(os.path.abspath(__file__))
# Evita adicionar o mesmo diretório mais de uma vez à lista de importações.
if project_dir not in sys.path:
    # Coloca a pasta do projeto na busca de módulos do Python.
    sys.path.insert(0, project_dir)

# Expõe a aplicação Flask com o nome que o servidor WSGI espera encontrar.
from app import app as application
