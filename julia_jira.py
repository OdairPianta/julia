import os
import time
import subprocess
import google.generativeai as genai
import requests
from requests.auth import HTTPBasicAuth
import re
import traceback
from dotenv import load_dotenv

load_dotenv()

JIRA_URL = os.getenv("JIRA_URL")
JIRA_USER = os.getenv("JIRA_USER")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
JIRA_JQL_QUERY = os.getenv("JIRA_JQL_QUERY")
GENAI_API_KEY = os.getenv("GENAI_API_KEY")

DIRECTORIES = [
    "models",
    "enums",
    "http",
    "jobs",
    "main.go",
    "notifications",
    "policies",
    "repository",
    "resources",
    "routes",
    "services",
    "tests",
]

SAMPLE_FILES = [
    "config/database.go",
    "http/controllers/sample_controller.go",
    "http/controllers/file_controller.go",
    "http/requests/create_sample_model_input.go",
    "http/requests/update_sample_model_input.go",
    "http/requests/create_file_input.go",
    "models/file.go",
    "models/sample_detail.go",
    "models/sample_item.go",
    "models/sample_model.go",
    "notifications/sample_notification.go",
    "policies/sample_policy.go",
    "repository/sample_repository.go",
    "routes/routes.go",
    "routes/samples.go",
    "tests/sample_test.go",
    "tests/factories/sample_factory.go",
    "tests/factories/sample_detail_factory.go",
]

genai.configure(api_key=GENAI_API_KEY)
GENERATION_CONFIG = {
    "temperature": float(os.getenv("TEMPERATURE")),
    "top_p": float(os.getenv("TOP_P")),
    "top_k": int(os.getenv("TOP_K")),
    "max_output_tokens": int(os.getenv("MAX_OUTPUT_TOKENS")),
    "response_mime_type": os.getenv("RESPONSE_MIME_TYPE")
}

def find_files_list(paths):
    files_list = []
    for path in paths:
        for root, _, filenames in os.walk(path):
            for filename in filenames:
                file_path = os.path.join(root, filename)
                files_list.append(file_path)
                with open(file_path, 'r') as file:
                    file_content = file.read()
    return files_list

def read_file_content(file_path):
    try:
        with open(file_path, 'r') as file:
            content = file.read()
        return content
    except FileNotFoundError:
        return "File not found."
    except IOError:
        return "Error reading file."
    
def find_files_content(files):
    files_content = ""
    for file_path in files:
        try:
            with open(file_path, 'r') as file:
                file_content = file.read()
                if file_content.strip():
                    files_content += f"{file_path}\n{file_content}\n\n"
                else:
                    print(f"Aviso: O arquivo '{file_path}' está em branco.")
        except FileNotFoundError:
            print(f"Erro: O arquivo '{file_path}' não foi encontrado.")
        except Exception as e:
            print(f"Erro ao ler o arquivo '{file_path}': {e}")

    return files_content

def extract_method_signatures(file_list):
    signatures = []

    for filename in file_list:
        content = read_file_content(filename)
        extracted_signatures = []

        for line in content.splitlines():
            stripped_line = line.strip()
            if stripped_line.startswith("func "):
                extracted_signatures.append(stripped_line + "/*...*/}")

        if extracted_signatures:
            signatures.append(f"{filename}\n" + "\n".join(extracted_signatures))

    return "\n\n".join(signatures)

def clean_response(response):
    return response.replace("```go", "").replace("``go", "").replace("`` go", "").replace("```", "").replace("``", "")

def extract_algorithm(response_text):
    code_pattern = re.compile(r'```(?:\w+\n)?(.*?)```', re.DOTALL)
    match = code_pattern.search(response_text)
    
    if match:
        return match.group(1).strip()
    else:
        return clean_response(response_text)

def clean_file_response(response):
    return response.replace(" - ", "").replace("- ", "").strip()

def slugify(text):
    text = text.lower()
    text = re.sub(r'\s+', '-', text) 
    text = re.sub(r'[^\w\-]', '', text)
    return text

def branch_exists_locally(branch_name):
    result = subprocess.run(["git", "branch", "--list", branch_name], capture_output=True, text=True)
    return branch_name in result.stdout

def branch_exists_remotely(branch_name):
    result = subprocess.run(["git", "ls-remote", "--heads", "origin", branch_name], capture_output=True, text=True)
    return branch_name in result.stdout

def git_checkout_branch(branch_name):    
    if branch_exists_locally(branch_name):
        print(f"Branch local {branch_name} já existe. Fazendo checkout.")
        subprocess.run(["git", "checkout", branch_name], check=True)
    elif branch_exists_remotely(branch_name):
        print(f"Branch remota {branch_name} já existe. Fazendo checkout e pull.")
        subprocess.run(["git", "checkout", branch_name], check=True)
        subprocess.run(["git", "pull", "origin", branch_name], check=True)
    else:
        print(f"Criando nova branch: {branch_name}")
        subprocess.run(["git", "checkout", "-b", branch_name], check=True)
    
    return branch_name

def extract_text_from_description(description):
    plain_text = ""
    if 'content' in description:
        for block in description['content']:
            if 'content' in block:
                for content_item in block['content']:
                    if content_item.get('type') == 'text':
                        plain_text += content_item.get('text', '') + "\n"
    return plain_text.strip()

def get_jira_issues_for_user(jira_url, jira_user, jira_api_token, jql_query):
    search_url = f"{jira_url}/rest/api/3/search"
    
    headers = {"Accept": "application/json"}
    auth = HTTPBasicAuth(jira_user, jira_api_token)
    
    params = {"jql": jql_query, "maxResults": 1, "fields": "summary,description"}
    
    response = requests.get(search_url, headers=headers, params=params, auth=auth)

    print(response.json())
    
    if response.status_code == 200:
        issues_data = response.json()
        if issues_data['issues']:
            first_issue = issues_data['issues'][0]
            issue_key = first_issue['key']
            title = first_issue['fields']['summary']
            description = extract_text_from_description(first_issue['fields']['description'])
            return issue_key, title, description
        else:
            return None, None, None
    else:
        raise Exception(f"Erro ao buscar tarefas: {response.status_code} {response.text}")

def clean_response(response):
    return response.replace("```go", "").replace("``go", "").replace("`` go", "").replace("```", "").replace("``", "")

def clean_file_response(response):
    return response.replace(" - ", "").replace("- ", "").strip()

def list_transitions(jira_url, jira_user, jira_api_token, issue_key):
    transitions_url = f"{jira_url}/rest/api/3/issue/{issue_key}/transitions"
    
    headers = {"Accept": "application/json"}
    auth = HTTPBasicAuth(jira_user, jira_api_token)
    
    response = requests.get(transitions_url, headers=headers, auth=auth)
    
    if response.status_code == 200:
        transitions_data = response.json()
        return transitions_data.get('transitions', [])
    else:
        raise Exception(f"Erro ao buscar transições para a tarefa {issue_key}: {response.status_code} {response.text}")

def transition_to_review(jira_url, jira_user, jira_api_token, issue_key, transition_name="Review"):
    transitions = list_transitions(jira_url, jira_user, jira_api_token, issue_key)
    
    transition_id = next((t['id'] for t in transitions if t['name'].lower() == transition_name.lower()), None)
    
    if transition_id:
        transitions_url = f"{jira_url}/rest/api/3/issue/{issue_key}/transitions"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        auth = HTTPBasicAuth(jira_user, jira_api_token)
        payload = {
            "transition": {
                "id": transition_id
            }
        }
        response = requests.post(transitions_url, headers=headers, auth=auth, json=payload)
        if response.status_code == 204:
            print(f"Tarefa {issue_key} foi movida para o status 'Review'.")
        else:
            raise Exception(f"Erro ao mover a tarefa {issue_key} para 'Review': {response.status_code} {response.text}")
    else:
        print(f"Transição para 'Review' não encontrada para a tarefa {issue_key}.")

def get_branch_name(issue_key, title, description):
    model = get_model("Forneça o nome da branch que deve ser utilizado.")
    chat_session = model.start_chat()

    branch_name = f"{issue_key}-{slugify(title)}"
    
    message = f"Considerando a tarefa \nTitulo: {title}\n {description}\n\nQual o nome da branch que deve ser utilizado? Se não ficar claro qual a branch, use este nome {branch_name} Responda com somente o nome da branch"
    response = chat_session.send_message(message)

    branch_name = clean_file_response(clean_response(response.text))
    branch_name = branch_name if branch_name == "" else f"{issue_key}-{slugify(title)}"
    return branch_name

def check_go_build_main():
    try:
        result = subprocess.run(
            ["go", "build", "-o", "/dev/null", "main.go"], 
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            print("Compilação bem-sucedida.")
            return ""
        else:
            print("Erro na compilação.")
            print("Saída:", result.stdout)
            print("Erro:", result.stderr)
            return result.stderr
    except subprocess.TimeoutExpired:
        print("A compilação foi encerrada após 5 segundos.")
        return ""
    except subprocess.CalledProcessError as e:
        print("Ocorreu um erro durante a compilação.")
        print("Código de retorno:", e.returncode)
        print("Erro:", e.stderr)
        return f"Erro: {e.stderr}"
    
def get_model(system_instruction):
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        generation_config=GENERATION_CONFIG,
        system_instruction=system_instruction
    )
    return model

def format_with_goimports(file_path):
    try:
        subprocess.run(["goimports", "-w", file_path], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Erro ao formatar o arquivo {file_path} com goimports: {e}")
    except Exception as e:
        print(f"Erro inesperado ao tentar formatar o arquivo {file_path} com goimports: {e}")

def print_token_count(model, chat_session):
    token_count = model.count_tokens(chat_session.history)
    print(f"Token count {token_count}")

def generate_code(description):
    description = description + """\n\nResultados esperados:
    Criar ou atualizar model, controller, requests, policy, repository, routes e outros arquivos
    Atualizar config/database.go caso sejam criadas ou alterados models
    Atualizar routes/routes.go caso sejam criadas ou alteradas rotas
    Criar testes para todos as funções do controller
    Criar arquivos com a mesma estrutura do sample"""

    files_list = find_files_list(DIRECTORIES)
    file_list_string = "\n".join(files_list)
    method_signatures = extract_method_signatures(files_list)
    print(f"Assinaturas de métodos extraídas de {len(files_list)} arquivos.")
    
    model = get_model("Você em um desenvolvedor especialista em GOLANG. Considere os arquivos e métodos do projeto abaixo\n" + method_signatures)
    chat_session = model.start_chat()

    sample_files_content = find_files_content(SAMPLE_FILES)
    second_message = f"Considere que será executada a tarefa:\n {description}\n\nSiga o padrão de código dos arquivos a seguir.\n\n{sample_files_content}. \n\nListe os arquivos que serão criado e alterados para atender o escopo da tarefa conforme arquivos de exemplo enviados acima. Retorne somente a lista de arquivos, sem formatações ou outros dados"
    response = chat_session.send_message(second_message)
    print(f"Lista de arquivos a serem criados e alterados:\n {response.text}")
    create_update_files_string = clean_response(response.text)
    create_update_file_list = create_update_files_string.split("\n")
    
    for file_path in create_update_file_list:
        file_path = clean_file_response(file_path)
        if file_path == "":
            continue

        if os.path.exists(file_path):
            with open(file_path, 'r') as file:
                existing_content = file.read()
            print(f"Arquivo {file_path} já existe. Enviando conteúdo atual para atualização.")
            message = f"O arquivo {file_path} já existe com o seguinte conteúdo:\n{existing_content}\nAtualize o arquivo para atender o escopo da tarefa. Responda somente com o código. Siga a estrutura dos arquivos sample existentes."
        else:
            print(f"Criando arquivo {file_path}")
            message = f"Crie o arquivo {file_path}. Responda somente com o código. Siga a estrutura dos arquivos sample existentes."


        response = chat_session.send_message(message)
        file_content = extract_algorithm(response.text)

        try:
            with open(file_path, 'w') as file:
                file.write(file_content)
            print(f"Arquivo {file_path} criado")
            format_with_goimports(file_path)
            # git_add_file(file_path)
        except Exception as e:
            print(f"Falha ao criar o arquivo {file_path}: {str(e)}")

        # break  # Apenas para criar o primeiro arquivo, remover para processar todos
    print_token_count(model, chat_session)
    # attempt_go_build_with_correction(chat_session)
    commit_message = get_commit_message(chat_session)
    return commit_message

def attempt_go_build_with_correction(chat_session, max_attempts=5):
    attempts = 0
    while attempts < max_attempts:
        error_message = check_go_build_main()
        
        if error_message == "":
            print("Compilação bem-sucedida na tentativa", attempts + 1)
            return True
        
        print(f"Tentativa {attempts + 1} falhou. Corrigindo erro...")

        first_message = (
            f"Erro encontrado: {error_message}\n"
            "Liste quais arquivos precisam ser criados ou modificados para corrigir o erro. "
            "Retorne somente a lista de arquivos."
        )
        response = chat_session.send_message(first_message)
        files_to_create_or_modify = clean_response(response.text.splitlines())

        for file_path in files_to_create_or_modify:
            file_path = clean_file_response(file_path)
            if file_path:
                correction_message = (
                    f"O erro foi: {error_message}. Corrija o arquivo '{file_path}' para resolver o problema. "
                    "Responda somente com o código corrigido."
                )
                response = chat_session.send_message(correction_message)
                corrected_code = clean_response(response.text)

                try:
                    with open(file_path, 'w') as file:
                        file.write(corrected_code)
                    print(f"Arquivo '{file_path}' corrigido e salvo.")
                except Exception as e:
                    print(f"Falha ao salvar o arquivo '{file_path}': {str(e)}")
        
        attempts += 1
    
    print("Número máximo de tentativas alcançado. A compilação ainda falha.")
    return False

    
def get_commit_message(chat_session):
    response = chat_session.send_message(f"Crie uma mensagem de commit considerando o contexto acima. Use ###Added para adições, ###Changed para alterações e ###Fixed para correções. Responda somente com a mensagem de commit")
    commit_message = clean_response(response.text)
    return commit_message

def git_add_file(file_path):
    try:
        subprocess.run(["git", "add", file_path], check=True)
        print(f"Arquivo {file_path} adicionado ao Git com sucesso.")
    except subprocess.CalledProcessError as e:
        print(f"Erro ao adicionar o arquivo {file_path} ao Git: {str(e)}")

def git_commit(message):
    try:
        subprocess.run(["git", "commit", "-m", message], check=True)
        print(f"Commit realizado com a mensagem: {message}")
    except subprocess.CalledProcessError as e:
        print(f"Erro ao realizar o commit: {str(e)}")

def git_push(branch_name):
    try:
        subprocess.run(["git", "push", "origin", branch_name], check=True)
        print(f"Push realizado com sucesso na branch: {branch_name}")
    except subprocess.CalledProcessError as e:
        print(f"Erro ao realizar o push: {str(e)}")

def main():
    processed_tasks = set()

    while True:
        try:
            issue_key, title, description = get_jira_issues_for_user(JIRA_URL, JIRA_USER, JIRA_API_TOKEN, JIRA_JQL_QUERY)
            print(issue_key, title, description)
            if issue_key and title and description:
                if issue_key not in processed_tasks:
                    print(f"Nova tarefa: {issue_key} - {title}")

                    processed_tasks.add(issue_key)
                    
                    branch_name = get_branch_name(issue_key, title, description)
                    print(f"Branch name: {branch_name}")
                    
                    git_checkout_branch(branch_name)
                    print(f"Checkout para {branch_name}")

                    task_description = f"{title}\n\n{description}"
                    
                    commit_message = generate_code(task_description)
                    print(f"Mensagem de commit: {commit_message}")

                    git_commit(commit_message)

                    git_push(branch_name)
                    print(f"git push {branch_name}")

                    transition_to_review(JIRA_URL, JIRA_USER, JIRA_API_TOKEN, issue_key)

                else:
                    print(f"Tarefa já processada: {issue_key}")
            else:
                print(f".", end="")
        except Exception as e:
            print(f"Erro: {str(e)}")
            traceback.print_exc()

        time.sleep(5)

if __name__ == "__main__":
    main()
