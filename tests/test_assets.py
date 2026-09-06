import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(HERE, "assets", "hello-algo")


def _all_images():
    out = []
    for root, _dirs, files in os.walk(ASSETS):
        for name in files:
            if name.lower().endswith((".png", ".gif", ".jpg")):
                out.append(os.path.join(root, name))
    return out


def test_assets_dir_exists():
    assert os.path.isdir(ASSETS)


def test_license_is_vendored():
    # CC BY-NC-SA 4.0 要求署名；授權原文必須跟著圖一起留在 repo 裡。
    with open(os.path.join(ASSETS, "LICENSE"), encoding="utf-8") as f:
        assert "Attribution-NonCommercial-ShareAlike 4.0" in f.read()


def test_image_count():
    assert len(_all_images()) == 506


def test_known_images_present():
    for rel in [
        "chapter_array_and_linkedlist/array.assets/array_definition.png",
        "chapter_searching/binary_search.assets/binary_search_step1.png",
        "chapter_tree/avl_tree.assets/avltree_rotation_cases.png",
    ]:
        assert os.path.isfile(os.path.join(ASSETS, rel)), rel
