from pathlib import Path

import pytest

from app.core.skills_loader import SkillLoader

SKILLS_DIR = Path(__file__).parent.parent / "skills"


def test_loads_real_academic_skill():
    meta, body = SkillLoader.load_skill(SKILLS_DIR / "academicextraction")
    assert "name" in meta and "description" in meta
    assert len(body) > 0


@pytest.mark.parametrize("skill_dir", [p for p in SKILLS_DIR.iterdir() if (p / "SKILL.md").exists()])
def test_all_bundled_skills_parse(skill_dir):
    meta, body = SkillLoader.load_skill(skill_dir)
    assert meta.get("name"), f"{skill_dir} missing name"
    assert body.strip()


def test_missing_skill_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        SkillLoader.load_skill(tmp_path)


def test_missing_frontmatter_raises(tmp_path):
    (tmp_path / "SKILL.md").write_text("# No frontmatter here\nJust text.")
    with pytest.raises(ValueError):
        SkillLoader.load_skill(tmp_path)


def test_missing_required_fields_raises(tmp_path):
    (tmp_path / "SKILL.md").write_text("---\nname: x\n---\nBody but no description.")
    with pytest.raises(ValueError):
        SkillLoader.load_skill(tmp_path)
