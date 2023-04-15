import os

import dotenv
dotenv.load_dotenv()
import re
from utils import model_interaction
import subprocess
from local import LocalCache


print(os.environ["PINECONE_API_KEY"])

codebase_memory = LocalCache("CodebaseMemory")
all_codebase_signatures = {} # {filename: [signature1, signature2, ...], ...}
all_pinecone_memory = LocalCache("ActionsMemory")
all_memory = []

INITIAL_PLANNING_AGENT_PROMPT_FORM = """
GOAL:
{goal}.

CONSTRAINTS:
You are on a fresh install of Arch linux, with only command line access.
Final product must have thorough test coverage.

TASK LIST FORMAT:
Task 1. <Task name>: <Task description>
Task 2. <Task name>: <Task description>
...

FULL TASK LIST:
"""

SUBTASKER_PROMPT_FORM = """
GOAL:
{goal}

CURRENT TASK LIST:
{task_list}

CONSTRAINTS:
You are on a fresh install of Arch linux, with only command line access.
Final product must have thorough test coverage.

CURRENT TASK: Task {task_number}.

SUBTASK LIST FORMAT:
Subtask 1. <Subtask name>: <Subtask description>

TASK {task_number} SUBTASKS:
"""

SUBTASK_CATEGORIZER_PROMPT_FORM = """
FINAL GOAL:
{goal}

CURRENT TASK LIST:
{subtask_list}

Which of the following categories best describes the actions needed for the current task?

1. Writing code
2. Sequence of terminal commands
3. Debugging
4. Research
5. Multiple categories

Respond only with the number of the category.

Answer:
"""


RELEVANT_CODE_PROMPT_FORM = """
FINAL GOAL:
{goal}

CURRENT TASK:
{current_task}

These are signatures of some of the files, functions and classes in the codebase:

{codebase_signatures}

Write the signatures of the functions and classes in the codebase most relevant to the current task, if there are any.
If there are no relevant functions or classes, write "None".
Make sure to write them in the same format they are in above, with the filename followed by the functions/classes.

RESPONSE:
"""

SUPERVISOR_ADVICE_PROMPT_FORM = """
FINAL GOAL:
{goal}

CURRENT TASK:
{current_task}

RELEVANT RECENT ACTIONS:
{recent_actions}

RELEVANT LONG-TERM MEMORIES:
{long_term_memories}

Message the agent asking him to perform the current task, including any relevant information or advice.
MESSAGE:
"""


WRITE_CODE_PROMPT_FORM = """
FINAL GOAL:
{goal}

CURRENT TASK:
{current_task}

EXISTING FUNCTIONS/CLASSES:
{relevant_code}

SUPERVISOR_ADVICE:
{supervisor_advice}

Using the above goal, code snippets and advice, write python code to perform the following subtask:
{subtask_string}

You may use any functions or classes from the codebase, or write new ones. Make sure your code is compatible with the existing codebase.
Your response should be in the following format:

File: <filename>.py
Code:
<code>

If there are multiple files to be written to, separate them with a line of dashes.
Your code should be a complete solution; do not leave any TODOs or temporary code.
Each function must specify its return type using a type hint.

COMPLETED CODE:
"""


EXECUTE_COMMANDS_PROMPT_FORM = """
FINAL GOAL:
{goal}

CURRENT TASK:
{current_task}

EXISTING FUNCTIONS/CLASSES:
{relevant_code}

SUPERVISOR_ADVICE:
{supervisor_advice}

Using the above goal, code snippets and advice, execute the terminal commands necessary to perform the following subtask:
{subtask_string}

Write the next command, followed by a new line and "EXECUTENOW".
You will then be prompted with the command's output, after which you can either execute another command, mark the task as completed by running "END", or mark the task as failed by running "FAIL".

COMMAND:
"""



model = "text-davinci-003"
max_tokens = 4096

        
def subtasks_to_string(subtasks):
    return '\n'.join([f"Subtask {i + 1}. {subtask}: {subtask_description}" for i, (subtask, subtask_description) in enumerate(subtasks)])


def main(main_goal="Write a 2d raytracer in C++, with shadows, reflections and refractions.", verbose=True):
    main_goal = main_goal.strip('.')

    print("Planning High-Level Tasks...")
    planning_agent_prompt = INITIAL_PLANNING_AGENT_PROMPT_FORM.format(goal=main_goal)
    tasks_string = model_interaction.model_call(planning_agent_prompt, model=model, temperature=0.7, max_tokens=400)
    print("\nTASK LIST:")
    print(tasks_string)

    task_list = re.findall('Task (\d+?)\. (.*?):(.*?)\n', tasks_string)
    
    for task_number, task, task_description in task_list:

        print(f"\nPlanning Task {task_number} Subtasks...")
        subtasks_string = model_interaction.model_call(SUBTASKER_PROMPT_FORM.format(goal=main_goal, task_list=tasks_string, task_number=task_number),
                                                    model=model, temperature=0.7, max_tokens=400)
        print("\nSUBTASK LIST:")
        print(subtasks_string)

        subtasks = re.findall('Subtask \d*?\.\s*(.*?):(.*?)\n', subtasks_string)

        res = len(re.findall("TASK", subtasks_to_string(subtasks)))
        if res > 0:
            subtasks_string = subtasks_string.split("\nTASK")[0].strip()

        
        while len(subtasks) > 0:

            current_subtask_category = model_interaction.model_call(SUBTASK_CATEGORIZER_PROMPT_FORM.format(goal=main_goal, subtask_list=re.sub("Subtask", "Task", subtasks_to_string(subtasks))),
                                                    model=model, temperature=0.7, max_tokens=400)
            print("\nCURRENT SUBTASK CATEGORY:")
            print(current_subtask_category)

            current_subtask_category = re.search('(\d*)', current_subtask_category)
            current_subtask_category = int(current_subtask_category.group()) if current_subtask_category else None

            if current_subtask_category == 5:

                print("SPLITTING SUBTASK 1 INTO MULTIPLE SUBTASKS...")
                subtasker_prompt = SUBTASKER_PROMPT_FORM.format(goal=main_goal, task_list=re.sub("Subtask", "Task", subtasks_to_string(subtasks)), task_number=1)
                subtasks_to_append = model_interaction.model_call(subtasker_prompt,
                                                        model=model, temperature=0.7)
                subtasks_to_append = re.findall('Subtask (d*?)\.\s*?(.?):(.?)', subtasks_to_append)
                subtasks = []
                for subtask in subtasks_to_append:
                    subtasks.append(subtask)
                for subtask in subtasks[:1]:
                    subtasks.append(subtask)
                print("NEW SUBTASK LIST:")
                print(subtasks_to_string(subtasks))
                new_memory_string = "I split subtask 1 into these subtasks:" + subtasks_to_string(subtasks).replace('\n', ', ')
                all_memory.append(new_memory_string)
                all_pinecone_memory.add(new_memory_string)
                continue
            
            
            codebase_signatures_string = "\n".join(["{filename}:\n{functions}}".format(
                filename=filename,
                functions=('\n'.join([f"    - {sig}" for sig in signatures]))) for filename, signatures in all_codebase_signatures.items()])

            if verbose:
                print("\nAll codebase signatures:")
                print(codebase_signatures_string + '\n' if len(all_codebase_signatures) > 0 else "None")

            if len(all_codebase_signatures) > 0:
                relevant_code_prompt = RELEVANT_CODE_PROMPT_FORM.format(
                    goal=main_goal,
                    current_task=task + ": " + task_description,
                    codebase_signatures=(codebase_signatures_string))
                relevant_code = model_interaction.model_call(relevant_code_prompt, model=model, temperature=0.7)
            else:
                relevant_code = "None"
            
            short_term_memories = all_memory[-5:]
            short_term_memories = '\n'.join([f"- {memory}" for memory in short_term_memories])
            long_term_memories = all_pinecone_memory.get_relevant(subtasks_to_string(subtasks).split('Subtask')[1], 10)
            long_term_memories = '\n'.join([f"- {memory}" for memory in long_term_memories])

            supervisor_advice_prompt = SUPERVISOR_ADVICE_PROMPT_FORM.format(
                goal=main_goal,
                current_task=task,
                recent_actions=short_term_memories,
                long_term_memories=long_term_memories)
            supervisor_advice = model_interaction.model_call(supervisor_advice_prompt, model=model, temperature=0.7, max_tokens=400)
            
            if verbose:
                print("RELEVANT CODE:")
                print(relevant_code)
                print("SUPERVISOR ADVICE:")
                print(supervisor_advice)
            
            if current_subtask_category == 1:
                
                print("WRITING CODE...")

                write_code_prompt = WRITE_CODE_PROMPT_FORM.format(goal=main_goal, current_task=task, relevant_code=relevant_code, supervisor_advice=supervisor_advice, subtask_string=subtasks_string)
                code_output = model_interaction.model_call(write_code_prompt,
                                                        model=model, temperature=0.7, max_tokens=max_tokens)
                py_function_regex = "\ndef (.*?):\s*\n"
                py_class_regex = "\nclass (.*?):\s*\n"
                files_to_write = re.findall("File: (.*?)\n", code_output)
                i = 0
                for file_code in code_output.split('File: '):
                    if file_code.strip() == '':
                        continue
                    file_functions = re.findall(py_function_regex, file_code)
                    file_classes = re.findall(py_class_regex, file_code)
                    file_name = files_to_write[i]
                    all_codebase_signatures[file_name] = file_functions + file_classes
                    with open(file_name, 'w') as f:
                        f.write(file_code.split('Code: \n')[1].strip())
                    new_memory_string = f"I wrote these functions and classes in {file_name}:" + ', '.join(file_functions) + '; ' + ', '.join(file_classes)
                    all_memory.append(new_memory_string)
                    all_pinecone_memory.add(new_memory_string)
                    i += 1
                subtasks = subtasks[1:]
                continue
            
            elif current_subtask_category == 2:
                print("EXECUTING TERMINAL COMMANDS...")
                terminal_command_prompt = EXECUTE_COMMANDS_PROMPT_FORM.format(
                    goal=main_goal,
                    current_task=task,
                    relevant_code=relevant_code,
                    supervisor_advice=supervisor_advice,
                    subtask_string=subtasks_string)
                while True:
                    terminal_command = model_interaction.model_call(terminal_command_prompt, model=model, temperature=0.7, max_tokens=400,
                                                                    stop=['EXECUTENOW'])
                    if terminal_command.strip() == 'END':
                        command_result = True
                        break
                    if terminal_command.strip() == 'FAIL':
                        command_result = False
                        break
                    print("TERMINAL COMMAND:")
                    print(terminal_command)
                    command_output = subprocess.run(terminal_command, shell=True, stdout=subprocess.PIPE).stdout.decode('utf-8')
                    os.system(terminal_command)
                    new_memory_string = f"I ran this terminal command: {terminal_command} and got this output: {command_output}"
                    all_memory.append(new_memory_string)
                    all_pinecone_memory.add(new_memory_string)
                    terminal_command_prompt = terminal_command_prompt + f"{terminal_command}\nEXECUTENOW\n\nCommand output:\n{command_output}\n\nCOMMAND:\n"
                if not command_result:
                    quit()
                subtasks = subtasks[1:]
                continue
            else:
                quit()

main()