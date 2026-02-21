# src/services/validator.py
from llama_index.core import PromptTemplate
from src.models.judgement import IdentityVerdict
from src.custom_program import LocalStructuredProgram
# from src.pipeline.context import PipelineContext # Type hint only

class SemanticValidator:
    def __init__(self, ctx):
        self.ctx = ctx
        self.llm = ctx.llm # Наш SmartLlamaLLM

        # --- ПРОМПТ ДЛЯ ЛОКАЦИЙ ---
        self.loc_prompt = PromptTemplate(
            "You are a Spatial Logic Engine. Analyze if Location A and Location B are the same place.\n\n"
            "LOCATION A: '{name_a}'\n"
            "Description A: {desc_a}\n\n"
            "LOCATION B: '{name_b}'\n"
            "Description B: {desc_b}\n\n"
            "CRITICAL RULES:\n"
            "1. CONTRADICTIONS: If A is 'indoors' and B is 'outdoors' (e.g., Room vs Meadow) -> FALSE.\n"
            "2. SCALE: If A is a container of B (e.g. 'Castle' vs 'Throne Room') -> FALSE (Keep separate).\n"
            "3. SYNONYMS: 'The Great Hall' == 'The Hall' -> TRUE.\n"
            "4. AMBIGUITY: If descriptions are empty, rely strictly on name uniqueness.\n"
        )
        
        self.loc_program = LocalStructuredProgram(
            output_cls=IdentityVerdict,
            llm=self.llm,
            prompt=self.loc_prompt,
            verbose=False
        )

    def validate_location_merge(self, 
                              cand_name: str, cand_desc: str,
                              target_name: str, target_desc: str) -> bool:
        """
        Возвращает True, только если LLM уверен, что это одно место.
        """
        # 1. Быстрый отсев совсем разных имен, если Fuzzy не справился
        # (Например, если Fuzzy дал низкий скор, но мы всё равно решили проверить)
        # Но здесь мы полагаемся на то, что кандидат уже прошел Fuzzy-отбор репозитория.

        try:
            verdict: IdentityVerdict = self.loc_program(
                name_a=cand_name, desc_a=cand_desc or "No description",
                name_b=target_name, desc_b=target_desc or "No description"
            )
            
            # Логирование "чудес" валидации
            if verdict.is_same:
                 print(f"   🤖 Validator MERGED: '{cand_name}' + '{target_name}' | {verdict.reason}")
            else:
                 print(f"   🛡️ Validator REJECTED: '{cand_name}' vs '{target_name}' | {verdict.reason}")

            return verdict.is_same

        except Exception as e:
            print(f"Validation Error: {e}")
            return False
        