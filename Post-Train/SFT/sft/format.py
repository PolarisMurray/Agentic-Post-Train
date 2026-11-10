"""How a tarjectory is rendered into text for the student model"""

"""Training and (later) inference must use exactly the same format"""

from __future__ import annotations

from dataclasses import dataclass

@dataclass
class ChatFormat:

    # chat tags of the student model (DeepSeek-R1-Distill-Qwen)

    bos: str = "<｜begin▁of▁sentence｜>"
    user: str = "<｜User｜>"
    assistant: str = "<｜Assistant｜>"
    tool 
    eos: str = "<｜end▁of▁sentence｜>"


    include_reasoning: bool = True

    def special_tokens(self) -> list[str]:
        return [self.bos, self.user, self.assistant, self.eos]