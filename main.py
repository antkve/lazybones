import os
import unittest

import dotenv
dotenv.load_dotenv()
import regex as re
from utils import model_interaction
import subprocess
from local import LocalCache
import tools.browsing
import argparse
import prompt_forms


class TaskComplete(Exception):
    pass
DEFAULT_MODEL = "text-davinci-003" #"gpt-3.5-turbo" 
DEFAULT_GOAL = "Write a 2D raytracing library in C++ for use in 2D platformers, complete with shadows, reflections and refractions."
max_tokens = 4096

def subtasks_to_string(subtasks, current_subtask_number=None):
    subtask_strings = [f"- {subtask.strip()}" for subtask in subtasks]
    if current_subtask_number is not None:
        subtask_strings[current_subtask_number - 1] += " (Current subtask)"
    return '\n'.join(subtask_strings)

def get_most_possible_recent(source_string_list, k):
    outputs = []
    for source_string in source_string_list[::-1]:
        output_string = '\n'.join(outputs)
        if len(output_string + source_string) <= k:
            outputs.append(source_string)
        else:
            break
    output_string = '\n'.join(outputs[::-1])
    return output_string

def tasks_to_string(tasks, current_task_number=None):
    task_strings = [f"Task {i + 1}. {task.strip()}: {task_description}" for i, (task, task_description) in enumerate(tasks)]
    if current_task_number is not None:
        task_strings[current_task_number - 1] += " (Current task)"
    return '\n'.join(task_strings)

def run(cmd):
    completed = subprocess.run(["powershell", "-Command", cmd], stdout=subprocess.PIPE).stdout.decode('utf-8')
    return completed

def get_supervisor_advice(environment, main_goal, task, task_description, subtasks, all_actions, actions_memory, model):
    long_term_memories = actions_memory.get_relevant('\n'.join(all_actions[-5:]), 50) if len(all_actions) > 5 else []
    supervisor_advice_prompt = prompt_forms.SUPERVISOR_ADVICE_PROMPT_FORM.format(
        environment=environment,
        goal=main_goal, 
        current_task=f"{task}: {task_description}",
        current_subtasks=subtasks_to_string(subtasks),
        recent_actions= get_most_possible_recent(all_actions, 4000), # '\n'.join(command_strings[-5:]),
        long_term_memories= get_most_possible_recent(long_term_memories, 4000) if long_term_memories else "None",
    )
    return model_interaction.model_call(supervisor_advice_prompt, model=model, temperature=0.5, max_tokens=400, model_name_for_verbose="supervisor")
            

def main(main_goal, environment="You are an experienced professional developer, on a Ubuntu machine. Use ONLY the actions provided; make directories with terminal commands. Do NOT use an IDE or text editor; use write_file, modify_code and so on instead. Do not research or google anything unless you have to; you have enough coding knowledge not to need to. Try to complete the subtasks one at a time.",
         terminal_input_output=False, model="text-davinci-003"):

    run("cd lazybones_workspace")

    codebase_memory = LocalCache("CodebaseMemory")
    codebase_signatures = {} # {filename: [signature1, signature2, ...], ...}

    main_goal = main_goal.strip('.')

    print("Planning High-Level Tasks...")
    planning_agent_prompt = prompt_forms.INITIAL_PLANNING_AGENT_PROMPT_FORM.format(environment=environment, goal=main_goal)
    planning_agent_output = model_interaction.model_call(planning_agent_prompt, model=model, temperature=0.7, max_tokens=400, model_name_for_verbose="planner")

    task_list = re.findall('Task \d+?\. (.*?):(.*?)\n', planning_agent_output)
    command_strings = []
    actions_memory = LocalCache("actions_memory")
    all_actions = []

    supervisor_counter = 0
    for task_number, (task, task_description) in enumerate(task_list):
        task_number = task_number + 1
        print(f"\nPlanning Task {task_number} Subtasks...")
        long_term_memories = actions_memory.get_relevant('\n'.join(all_actions[-5:]), 50) if len(all_actions) > 5 else []
        subtasks_output = model_interaction.model_call(
            prompt_forms.SUBTASKER_PROMPT_FORM.format(
                environment=environment,
                goal=main_goal, 
                task_list=tasks_to_string(task_list, task_number), 
                task_number=task_number, 
                task_name=task,
                recent_actions=get_most_possible_recent(all_actions, 4000),
                long_term_memories=get_most_possible_recent(long_term_memories, 4000) if long_term_memories else "None",
                task_description=task_description
            ),
            model=model, temperature=0.7, max_tokens=400, model_name_for_verbose="subtasker"
        )

        num_tasks_outputted = len(re.findall("TASK", subtasks_output))
        if num_tasks_outputted > 0:
            subtasks_output = subtasks_output.split("\nTASK")[0].strip()

        subtasks = re.findall('(?:\n|^)-\s?(.*?)\s*(?:\n|$)', subtasks_output, overlapped=True)
        supervisor_advice_output = get_supervisor_advice(environment, main_goal, task, task_description, subtasks, all_actions, actions_memory, model=model)

        while len(subtasks) > 0:
            base_executor_prompt = prompt_forms.EXECUTOR_PROMPT_FORM.format(
                environment=environment,
                actions=prompt_forms.ACTIONS,
                goal=main_goal,
                current_tasks=tasks_to_string(task_list, task_number),
                current_subtasks=subtasks_to_string(subtasks),
                supervisor_advice=supervisor_advice_output
            )
            commands_recent = get_most_possible_recent(command_strings, 6500)
            executor_prompt = base_executor_prompt + commands_recent
            # Command string format:
            # <thoughts>
            # ...
            # >THOUGHTS:
            executor_output = model_interaction.model_call(executor_prompt, model=model, temperature=0.7, max_tokens=1000, stop=[">ENDACTION"], model_name_for_verbose="executor")
            try:
                executor_thoughts = re.findall("^(.*?)>", executor_output, re.DOTALL)[0].strip()
                executor_action = re.findall(">ACTION:\n(.*?)$", executor_output, re.DOTALL)[0].strip()
                executor_action_name = executor_action.split(":")[0].strip()
                executor_action_arg_1 = executor_action.split('\n')[1].strip()
                executor_action_arg_2 = '\n'.join(executor_action.split('\n')[2:]).strip() if len(executor_action.split('\n')) > 2 else None
            except IndexError:
                executor_action_name = "INVALID"
            input("Press enter to continue with action...")

            if executor_action_name == "GOOGLE":
                res = tools.browsing.google_search(executor_action_arg_1)
                memory = f"I googled '{executor_action_arg_1}' and found {res}"
            elif executor_action_name == "BROWSE":
                res = tools.browsing.browse_website(executor_action_arg_1, executor_action_arg_2)
                memory = f"I browsed to {executor_action_arg_1} to answer the question \"{executor_action_arg_2}\" and got the following result: {res}"
            elif executor_action_name == "RUN_TERMINAL_COMMAND":
                # import sys 
                # print("Enter command output:")
                # inputlist = sys.stdin.readlines() 
                # print(inputlist)
                if executor_action_arg_2 is not None:
                    executor_action_arg_1 += "\n" + executor_action_arg_2
                res = ""
                for line in executor_action_arg_1.split("\n"):
                    res += "\n" + run(line) # res = input("Enter command output:")
                if len(res) > 2000:
                    res = res[:1000] + "..." + res[-1000:]
                res = res.strip()
                memory = f"I ran the command '{executor_action_arg_1}' and got the following result(s): {res if res != '' else 'Success'}"
            elif executor_action_name == "DO_NOTHING":
                res = "None"
                memory = "I did nothing."
            elif executor_action_name == "WRITE_FILE":
                res = tools.file_operations.write_to_file(executor_action_arg_1, executor_action_arg_2)
                new_functions = re.findall("(?:^|\n)def (.*?):\n", executor_action_arg_2, re.DOTALL)
                new_classes = re.findall("(class .*?):\n", executor_action_arg_2, re.DOTALL)
                codebase_signatures[executor_action_arg_1] = new_functions + new_classes
                memory = f"I added these new functions and classes to '{executor_action_arg_1}':\n{', '.join(new_functions)}; {', '.join(new_classes)}" if len(new_functions) > 0 or len(new_classes) > 0 else f"I added the following to '{executor_action_arg_1}':\n{executor_action_arg_2}"
            
            elif executor_action_name == "READ_FILE":
                res = tools.file_operations.read_file(executor_action_arg_1)
                memory = f"I read the file '{executor_action_arg_1}'"
            elif executor_action_name == "ADD_TO_FILE":
                res = tools.file_operations.write_to_file(executor_action_arg_1, executor_action_arg_2)
                new_functions = re.findall("(?:^|\n)def (.*?):\n", executor_action_arg_2, re.DOTALL)
                new_classes = re.findall("(class .*?):\n", executor_action_arg_2, re.DOTALL)
                codebase_signatures[executor_action_arg_1] = new_functions + new_classes
                memory = f"I added these new functions and classes to '{executor_action_arg_1}':\n{', '.join(new_functions)}; {', '.join(new_classes)}" if len(new_functions) > 0 or len(new_classes) > 0 else f"I added the following to '{executor_action_arg_1}':\n{executor_action_arg_2}"
            elif executor_action_name == "DELETE_FILE":
                res = tools.file_operations.delete_file(executor_action_arg_1)
                memory = f"I deleted the file '{executor_action_arg_1}'"
            elif executor_action_name == "MODIFY_CODE":
                code_text = tools.file_operations.read_file(executor_action_arg_1)
                res = model_interaction.edit_call(code_text, executor_action_arg_2, temperature=0.7, model_name_for_verbose="code editor")
                tools.file_operations.write_to_file(executor_action_arg_1, res)
                memory = f"I modified the file '{executor_action_arg_1}' based on the following instructions:\n{executor_action_arg_2}"
            elif executor_action_name == "MARK_TASK_COMPLETE":
                res = "Finished task '{task}'".format(task=f"{task}: {task_description}")
                memory = "I marked the task '{task}' as completed".format(task=f"{task}: {task_description}")
                subtasks = []
            elif executor_action_name == "ASK_SUPERVISOR":
                
                supervisor_memory_question_prompt = prompt_forms.SUPERVISOR_MEMORY_QUESTION_PROMPT_FORM.format(
                    question=executor_action_arg_1,
                    environment=environment,
                    goal=main_goal,
                    memory_chunk='\n- '.join(all_actions)
                )
                supervisor_memory_question_output = model_interaction.model_call(supervisor_memory_question_prompt, model=model, temperature=0.7, max_tokens=400, model_name_for_verbose="supervisor/advisor")
                
                code_chunk = ""
                for filename, signatures in codebase_signatures.items():
                    file_contents = tools.file_operations.read_file(filename)
                    code_chunk += '>>>' + filename + ' CONTENTS:\n\n' + file_contents + '\n\n'
                supervisor_code_question_prompt = prompt_forms.SUPERVISOR_CODE_QUESTION_PROMPT_FORM.format(
                    question=executor_action_arg_1,
                    environment=environment,
                    goal=main_goal,
                    code_chunk=code_chunk
                )
                supervisor_code_question_output = model_interaction.model_call(supervisor_code_question_prompt, model=model, temperature=0.7, max_tokens=400, model_name_for_verbose="supervisor/advisor")
                supervisor_question_prompt = prompt_forms.SUPERVISOR_QUESTION_PROMPT_FORM.format(
                    goal=main_goal,
                    task_list=tasks_to_string(task_list),
                    question=executor_action_arg_1,
                    subtask=subtasks[0][0],
                    supervisor_advice=supervisor_advice_output,
                    memory_summary=supervisor_memory_question_output,
                    code_summary=supervisor_code_question_output
                )
                    
                res = model_interaction.model_call(supervisor_question_prompt, model=model, temperature=0.7, max_tokens=400, stop=['==='], model_name_for_verbose="supervisor/advisor")
                memory = f"I asked the supervisor the question '{executor_action_arg_1}' and got the following reply: {res}"
            else:
                executor_action_name = "INVALID"
                res = "Error: Action not understood. Please try again. Make sure you include thoughts and an action."
            
            
            endaction_string = ""
            if executor_action_name != "INVALID":
                endaction_string = ">ENDACTION\n" 
                all_actions.append(memory)
                model_interaction.printlog(memory)
                if len(all_actions) > 5:
                    actions_memory.add(all_actions[-6])
            
            command_string = f"{executor_output}\n{endaction_string}OUTPUT:\n{res.strip()}\n\n>THOUGHTS:\n"
            supervisor_counter += 1
            if supervisor_counter % 3 == 0 and executor_action_name not in ["ASK_SUPERVISOR", "INVALID", "MARK_TASK_COMPLETE"]:
                supervisor_advice_output_momentary = get_supervisor_advice(environment, main_goal, task, task_description, subtasks, all_actions, actions_memory, model=model)
                command_string = command_string[:-12] + f"\nSUPERVISOR FEEDBACK:\n{supervisor_advice_output_momentary}" + command_string[-12:]
                # subtask_updater_prompt = prompt_forms.SUBTASK_UPDATER_PROMPT_FORM.format(
                #     environment=environment,
                #     goal=main_goal,
                #     task_list=tasks_to_string(task_list, task_number),
                #     command_strings='\n- ' + '\n- '.join([command_string] + command_strings[-5:]),
                #     subtask_list=subtasks_to_string(subtasks),
                # )
                # subtasks_output = model_interaction.model_call(subtask_updater_prompt, model=model, temperature=0.7, max_tokens=400, stop=['==='], model_name_for_verbose="subtask updater")
                # subtasks = re.findall('(?:\n|^)- (.*?)\n', subtasks_output)

            command_strings.append(command_string)

if __name__=="__main__":
    argparser = argparse.ArgumentParser()
    argparser.add_argument("--goal", type=str, default=DEFAULT_GOAL)
    argparser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    args = argparser.parse_args()

    main(args.goal, model=args.model)