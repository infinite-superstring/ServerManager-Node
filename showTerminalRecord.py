import os

session = input("session_id:")

with open(str(os.path.join(os.getcwd(), f'terminal_record/{session}.txt')), 'r+') as fd:
    while True:
        text = fd.read(1024)
        if text == "":
            break
        print(text, end='')