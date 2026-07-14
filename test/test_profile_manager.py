import os
import shutil
import tempfile
import pytest
from src.chatybot.profile_manager import ProfileManager, ProfileMeta

def test_read_meta_full():
    with tempfile.TemporaryDirectory() as tmpdir:
        profile_content = """# @name: Custom Profile Name
# @description: A custom profile description here
/model devstral_1
"""
        path = os.path.join(tmpdir, "test.chatdsl")
        with open(path, "w", encoding="utf-8") as f:
            f.write(profile_content)
            
        pm = ProfileManager(tmpdir)
        meta = pm.read_meta(path)
        
        assert meta.name == "Custom Profile Name"
        assert meta.description == "A custom profile description here"
        assert meta.source_path == path

def test_read_meta_name_only():
    with tempfile.TemporaryDirectory() as tmpdir:
        profile_content = """# @name: Only Name Profile
/model devstral_1
"""
        path = os.path.join(tmpdir, "test.chatdsl")
        with open(path, "w", encoding="utf-8") as f:
            f.write(profile_content)
            
        pm = ProfileManager(tmpdir)
        meta = pm.read_meta(path)
        
        assert meta.name == "Only Name Profile"
        assert meta.description == ""

def test_read_meta_none():
    with tempfile.TemporaryDirectory() as tmpdir:
        profile_content = """/model devstral_1
"""
        path = os.path.join(tmpdir, "test_none.chatdsl")
        with open(path, "w", encoding="utf-8") as f:
            f.write(profile_content)
            
        pm = ProfileManager(tmpdir)
        meta = pm.read_meta(path)
        
        # Name falls back to filename stem
        assert meta.name == "test_none"
        assert meta.description == ""

def test_read_meta_stops_at_code():
    with tempfile.TemporaryDirectory() as tmpdir:
        profile_content = """# @name: Right Name
/model devstral_1
# @name: Wrong Name
# @description: Wrong Description
"""
        path = os.path.join(tmpdir, "test.chatdsl")
        with open(path, "w", encoding="utf-8") as f:
            f.write(profile_content)
            
        pm = ProfileManager(tmpdir)
        meta = pm.read_meta(path)
        
        assert meta.name == "Right Name"
        assert meta.description == ""

def test_list_profiles():
    with tempfile.TemporaryDirectory() as tmpdir:
        pm = ProfileManager(tmpdir)
        
        # Create some mock profiles
        open(os.path.join(tmpdir, "b.chatdsl"), "w").close()
        open(os.path.join(tmpdir, "a.chatdsl"), "w").close()
        open(os.path.join(tmpdir, "not_profile.txt"), "w").close()
        
        profiles = pm.list_profiles()
        assert profiles == ["a.chatdsl", "b.chatdsl"]

def test_clone_profile():
    with tempfile.TemporaryDirectory() as tmpdir:
        pm = ProfileManager(tmpdir)
        src_path = os.path.join(tmpdir, "coding.chatdsl")
        with open(src_path, "w") as f:
            f.write("content here")
            
        dst_path = pm.clone_profile("coding", "my_coding")
        assert os.path.exists(dst_path)
        assert os.path.basename(dst_path) == "my_coding.chatdsl"
        
        with open(dst_path, "r") as f:
            assert f.read() == "content here"

def test_delete_profile():
    with tempfile.TemporaryDirectory() as tmpdir:
        pm = ProfileManager(tmpdir)
        path = os.path.join(tmpdir, "to_delete.chatdsl")
        open(path, "w").close()
        
        assert os.path.exists(path)
        pm.delete_profile("to_delete")
        assert not os.path.exists(path)

def test_export_import_roundtrip():
    with tempfile.TemporaryDirectory() as tmpdir1:
        with tempfile.TemporaryDirectory() as tmpdir_export:
            with tempfile.TemporaryDirectory() as tmpdir2:
                pm1 = ProfileManager(tmpdir1)
                pm2 = ProfileManager(tmpdir2)
                
                src = os.path.join(tmpdir1, "export_me.chatdsl")
                with open(src, "w") as f:
                    f.write("roundtrip content")
                    
                export_path = os.path.join(tmpdir_export, "exported.chatdsl")
                pm1.export_profile("export_me", export_path)
                assert os.path.exists(export_path)
                
                import_path = pm2.import_profile(export_path)
                assert os.path.exists(import_path)
                assert os.path.basename(import_path) == "exported.chatdsl"
                with open(import_path, "r") as f:
                    assert f.read() == "roundtrip content"

def test_seed_presets_idempotent():
    with tempfile.TemporaryDirectory() as tmpdir:
        pm = ProfileManager(tmpdir)
        pm.seed_presets()
        
        presets = pm.list_profiles()
        assert "coding.chatdsl" in presets
        assert "general.chatdsl" in presets
        assert "explorer.chatdsl" in presets
        
        # Modify coding.chatdsl
        coding_path = os.path.join(tmpdir, "coding.chatdsl")
        with open(coding_path, "w") as f:
            f.write("user modified content")
            
        # Reseed
        pm.seed_presets()
        
        # Verify it wasn't overwritten
        with open(coding_path, "r") as f:
            assert f.read() == "user modified content"

def test_resolve_path_by_alias():
    with tempfile.TemporaryDirectory() as tmpdir:
        pm = ProfileManager(tmpdir)
        path = os.path.join(tmpdir, "target.chatdsl")
        open(path, "w").close()
        
        resolved = pm._resolve_path("target")
        assert resolved == path
        
        resolved2 = pm._resolve_path("target.chatdsl")
        assert resolved2 == path

def test_resolve_path_not_found():
    with tempfile.TemporaryDirectory() as tmpdir:
        pm = ProfileManager(tmpdir)
        with pytest.raises(FileNotFoundError):
            pm._resolve_path("does_not_exist")
