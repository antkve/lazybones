
import pinecone
import utils.model_interaction as model_interaction
import json

class PineconeMemory(pinecone.Index):
    def __init__(self, name, pinecone_api_key, pinecone_region) -> None:
        dimension = 1536
        metric = "cosine"
        pod_type = "p1"
        pinecone.init(api_key=pinecone_api_key, environment=pinecone_region)
        if name not in pinecone.list_indexes():
            pinecone.create_index(name, dimension=dimension, metric=metric, pod_type=pod_type)
        super().__init__(name)
        pinecone_api_key = pinecone_api_key
        pinecone_region = pinecone_region
        # this assumes we don't start with memory.
        # for now this works.
        # we'll need a more complicated and robust system if we want to start with memory.
        self.vec_num = 0

    def add(self, data):
        vector = model_interaction.get_ada_embedding(data)
        # no metadata here. We may wish to change that long term.
        resp = self.index.upsert([(str(self.vec_num), vector, {"raw_text": data})])
        _text = f"Inserting data into memory at index: {self.vec_num}:\n data: {data}"
        self.vec_num += 1
        return _text

    def get_relevant_memories_from_current_context(self, current_context, top_k=5):
        vector = model_interaction.get_ada_embedding(current_context)
        results = self.query(vector, top_k=top_k, include_metadata=True)
        sorted_results = sorted(results.matches, key=lambda x: x.score)
        return [str(item['metadata']["raw_text"]) for item in sorted_results]
    

class BaseAgent():
    def __init__(self, name, model, temperature) -> None:
        self.name = name
        self.model = model
        self.temperature = temperature
        self.max_tokens = 8192 if self.model == 'gpt-4' else 4096
    
    def prompt(self, prompt):
        return model_interaction.model_call(prompt, model=self.model, temperature=self.temperature, max_tokens=self.max_tokens)
    

class OneShotAgent(BaseAgent):
    def __init__(self, name, model, temperature, one_shot_prompt) -> None:
        super().__init__(name, model, temperature)
        self.one_shot_prompt = one_shot_prompt
    
    def call(self, prompt):
        return self.prompt(self.one_shot_prompt + prompt)

class ContinuousAgent(BaseAgent):

    def __init__(self, name, model, temperature) -> None:
        super().__init__(name, model, temperature)
        self.short_term_memory_limit = 6
        self.long_term_memory = PineconeMemory(f"{name}_long_term_memory")
        self.short_term_memory = []

    def __add_event_to_short_term_memory(self, event_string):
        self.short_term_memory.append(event_string)
        if len(self.short_term_memory) > self.short_term_memory_limit:
            self.long_term_memory.add(self.short_term_memory[self.short_term_memory_limit])

    def __get_current_state(self):
        i = self.short_term_memory_limit
        while True:
            current_context = "\n".join(self.short_term_memory[:i])
            relevant_memories = self.long_term_memory.get_relevant_memories_from_current_context(current_context, i)
            prompt = self.intro_prompt + f"""

            RELEVANT EVENTS FROM LONG TERM MEMORY:

            {','.join(relevant_memories)}

            RECENT CONTEXT:

            {current_context}
            """

            if len(prompt) / 3.5 < self.max_tokens:  # 4 is the average chars per token
                break
            i -= 1
        return prompt

    
class DelegatorAgent(ContinuousAgent):
    def __init__(self, name, goal, available_agents = {},
                 temperature=0.7, model="gpt-3.5-turbo"):
        super().__init__(name, model, temperature)
        self.intro_prompt = """
        The Delegator agent is responsible for delegating subtasks to other agents.
        Given a set of subtasks for its task (which is selected to help accomplish the FINAL GOAL),
        it will assign an agent to the next subtask, and monitor that agent's progress. It will
        message the current agent with information that it sees in its 
        long-term memory if the information would help the agent with its task.
        It also queries the Knowledge agent with any question it has about the codebase, or
        when the current agent could use some help.

        AGENT FAILURE:
        If the agent fails, the Delegator 

        The Delegator's first action is choosing the agent for the first task.

        FINAL GOAL:
        {goal}

        OVERALL PLAN:
        {task_list}

        TASK {task_number} SUBTASKS:
        {subtask_list}

        AVAILABLE AGENTS:
        {available_agents}

        What is the name of the agent most well-fitted to accomplish this task?
        """