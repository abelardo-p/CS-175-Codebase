

def formatPrompt(system_prompt: str, assumption, schema: str, question: str) -> str:
    return [f"{system_prompt}\n\nSchema:\n{schema}\n\n{assumption}\n\n", \
            f"Question: {question}"]

def formatOutput(prefix: str, suffix: str, query_result):
    if query_result.startswith(prefix) and query_result.endswith(suffix):
        return query_result.split(prefix)[1].split(suffix)[0]
    elif query_result.startswith(prefix) and query_result.endswith(suffix + '\n'):
        return query_result.split(prefix)[1].split(suffix)[0]
    else:
        return query_result
    
def main():
    pass

if __name__ == '__main__':
    main()