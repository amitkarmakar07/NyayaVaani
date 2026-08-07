from crewai import Agent, Task, Crew, Process
from crewai.project import CrewBase, agent, task, crew
from src.nyayavaani_crew.tools import state_helpline_tool, department_lookup_tool, legal_rag_tool, twitter_handle_lookup_tool
from src.nyayavaani_crew.schemas import AnalyzerOutput, RouterOutput, WriterOutput, SocialMediaOutput
from crewai import LLM
from config import Config

def get_llm():
    return LLM(model=f"gemini/{Config.LLM_MODEL}", api_key=Config.GOOGLE_API_KEY, temperature=0.5)

@CrewBase
class NyayaVaaniCrew:
    """NyayaVaani Multi-Agent Civic Grievance Crew"""

    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'

    # --- AGENTS ---

    @agent
    def analyzer_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['analyzer_agent'],
            llm=get_llm(),
            verbose=True
        )

    @agent
    def router_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['router_agent'],
            tools=[state_helpline_tool, department_lookup_tool],
            llm=get_llm(),
            verbose=True
        )

    @agent
    def researcher_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['researcher_agent'],
            tools=[legal_rag_tool],
            llm=get_llm(),
            verbose=True
        )

    @agent
    def writer_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['writer_agent'],
            llm=get_llm(),
            verbose=True
        )

    @agent
    def social_media_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['social_media_agent'],
            tools=[twitter_handle_lookup_tool],
            llm=get_llm(),
            verbose=True
        )

    # --- TASKS ---

    @task
    def analyzer_task(self) -> Task:
        return Task(
            config=self.tasks_config['analyzer_task'],
            agent=self.analyzer_agent(),
            output_pydantic=AnalyzerOutput
        )

    @task
    def router_task(self) -> Task:
        return Task(
            config=self.tasks_config['router_task'],
            agent=self.router_agent(),
            output_pydantic=RouterOutput
        )

    @task
    def researcher_task(self) -> Task:
        return Task(
            config=self.tasks_config['researcher_task'],
            agent=self.researcher_agent()
        )

    @task
    def writer_task(self) -> Task:
        return Task(
            config=self.tasks_config['writer_task'],
            agent=self.writer_agent(),
            output_pydantic=WriterOutput
        )

    @task
    def social_media_task(self) -> Task:
        return Task(
            config=self.tasks_config['social_media_task'],
            agent=self.social_media_agent(),
            output_pydantic=SocialMediaOutput
        )

    # --- CREW ---

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True
        )
