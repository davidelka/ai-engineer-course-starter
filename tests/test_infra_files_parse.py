"""Every compose file and every Terraform folder in the repo at least parses.

The course was built where Docker Hub was blocked and no terraform binary existed, so no image
was built, no compose stack was started and no `terraform validate` ran. This is the floor we
CAN check offline: YAML/HCL syntax, compose services that reference a build or an image, and
pinned image tags (only Phoenix still uses :latest, on purpose, and is listed here).
"""

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = sorted(p for p in ROOT.rglob("compose*.y*ml") if ".git" not in p.parts and "fixtures" not in p.parts)
TF_DIRS = sorted({p.parent for p in ROOT.rglob("*.tf") if ".git" not in p.parts and "fixtures" not in p.parts})
UNPINNED_ON_PURPOSE = {"arizephoenix/phoenix:latest"}


@pytest.mark.parametrize("path", COMPOSE, ids=lambda p: str(p.relative_to(ROOT)))
def test_compose_parses_and_services_have_an_image_or_build(path):
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(doc.get("services"), dict) and doc["services"], "no services"
    for name, svc in doc["services"].items():
        assert "image" in svc or "build" in svc, f"service {name} has neither image nor build"
        img = svc.get("image", "")
        if img:
            if ":" not in img.split("/")[-1]:
                pytest.fail(f"service {name}: image {img} has no tag")
            if img.endswith(":latest") and img not in UNPINNED_ON_PURPOSE:
                pytest.fail(f"service {name}: {img} is not pinned")


@pytest.mark.parametrize("folder", TF_DIRS, ids=lambda p: str(p.relative_to(ROOT)))
def test_terraform_folder_parses(folder):
    hcl2 = pytest.importorskip("hcl2")
    for tf in sorted(folder.glob("*.tf")):
        with tf.open(encoding="utf-8") as f:
            hcl2.load(f)
