import re
from pathlib import Path
from typing import Dict, Any, Tuple
import yaml


class SkillLoader:
    """
    Parser compliant with the agentskills.io specification.
    Responsible for progressive disclosure: loading metadata first,
    and then injecting Markdown instructions dynamically at runtime.
    """

    @staticmethod
    def load_skill(skill_dir: Path) -> Tuple[Dict[str, Any], str]:
        """
        Parses a SKILL.md file and returns its metadata (frontmatter)
        and instruction body (markdown).
        """
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            raise FileNotFoundError(
                f"Missing specification file: SKILL.md not found in {skill_dir.absolute()}"
            )

        content = skill_file.read_text(encoding="utf-8")

        # Capture the YAML frontmatter bounded by ---
        pattern = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL | re.MULTILINE)
        match = pattern.match(content)

        if not match:
            raise ValueError(
                f"Format error in {skill_file}: Must start with a valid YAML frontmatter bounded by '---'."
            )

        frontmatter_str = match.group(1)
        body_content = match.group(2).strip()

        try:
            metadata = yaml.safe_load(frontmatter_str)
            if not isinstance(metadata, dict):
                raise ValueError("Frontmatter must be a key-value mapping.")
        except Exception as e:
            raise ValueError(f"YAML syntax error in frontmatter: {str(e)}")

        # Strict validation of required fields per agentskills.io
        if "name" not in metadata or "description" not in metadata:
            raise ValueError(
                "Specification violation: Both 'name' and 'description' are mandatory in SKILL.md frontmatter."
            )

        return metadata, body_content