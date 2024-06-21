def clean_message(message):
    # Lista de patrones a eliminar
    patterns = ["TERMINAR", "TERMINATE", "```", "html", "<body>", "</body>", "</html", "<html>", "<footer>", "</footer>", "<nav>", "</nav>", "<header>", "</header>", "<head>", "</head>"]

    # Iterar sobre la lista y aplicar el reemplazo
    for pattern in patterns:
        message = message.replace(pattern, "")

    return message