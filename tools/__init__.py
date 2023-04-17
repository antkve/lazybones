from . import file_operations
from tools.browsing import google_search

TOOL_LLM_MODEL = "gpt-3.5-turbo" # Model used in tools, such as for web page summaries.

BASE_TOOLS = {
    'do_nothing': {
        'readable': 'Do nothing',
        'function':(lambda: ''),
        'args': []},
    'task_complete': {
        'readable': 'Task complete (Shutdown)',
        'function':(lambda: print("Agent shutting down.") and quit()),
        'args': [('reason','<reason for shutting down>')]},
}

ORGANIZER_TOOLS = {
    'rearrange_tasks'
}

DEV_TOOLS = {
    'write_to_file': {
        'readable': 'Write to a file',
        'function': file_operations.write_to_file,
        'args': [('file_name', '<name of file>'), ('content', '<contents to write>')]}, 
    'read_from_file': { 
        'readable': 'Read from a file',
        'function':file_operations.read_file,    
        'args': [('file_name', '<name of file>')]},
    'run_python_file': {
        'readable': 'Run a python file',
        'function':(lambda: ''),
        'args': [('file_name', '<name of file>')]
    },

    'google_search': {
        'readable': 'Google search',
        'function': google_search,
        'args': [('input', '<string to search>')]},
}

def tool_list_to_string(tool_dict):
    tool_argument_descriptions = {tool_command: ', '.join(['"{}": "{}"'.format(arg_name, arg_desc) for arg_name, arg_desc in tool_dict[tool_command]['args']]) for tool_command in tool_dict.keys()}
    return '\n' + "\n".join([f'{i}. {tool_dict[command]["readable"]}: "{command}", args: ' + tool_argument_descriptions[i] for i, command in enumerate(tool_dict.keys())])