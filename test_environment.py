"""
Test script to validate environment configuration (TASK-ENV-0000).
Tests all environment variables and configuration loading.
"""

import sys
import os
from pathlib import Path

# Add autopiloot to path
sys.path.append('/Users/maarten/Projects/16 - autopiloot/agents')

def test_env_template_exists():
    """Test that .env.template file exists with required variables."""
    template_path = Path('/Users/maarten/Projects/16 - autopiloot/agents/.env.template')
    
    if not template_path.exists():
        print("❌ .env.template file not found")
        return False
    
    with open(template_path, 'r') as f:
        content = f.read()
    
    required_vars = [
        'OPENAI_API_KEY',
        'ASSEMBLYAI_API_KEY', 
        'YOUTUBE_API_KEY',
        'SLACK_BOT_TOKEN',
        'GOOGLE_SERVICE_ACCOUNT_PATH',
        'GCP_PROJECT_ID',
        'ZEP_API_KEY',
        'DRIVE_TRANSCRIPTS_FOLDER_ID',
        'DRIVE_SUMMARIES_FOLDER_ID'
    ]
    
    missing_vars = []
    for var in required_vars:
        if var not in content:
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ .env.template missing variables: {', '.join(missing_vars)}")
        return False
    
    print("✅ .env.template exists with all required variables")
    return True

def test_env_loader_import():
    """Test that env_loader can be imported."""
    try:
        from autopiloot.core.env_loader import env_loader, get_required_var, get_config_value
        print("✅ Environment loader imports successfully")
        return True
    except ImportError as e:
        print(f"❌ Failed to import env_loader: {str(e)}")
        return False

def test_settings_yaml_access():
    """Test that settings.yaml can be loaded."""
    try:
        from autopiloot.core.env_loader import env_loader
        config = env_loader.load_settings_config()
        
        # Test access to known config values
        scraper_limit = env_loader.get_config_value("scraper.daily_limit_per_channel", 10)
        llm_model = env_loader.get_config_value("llm.default.model", "gpt-4.1")
        
        print(f"✅ Settings loaded: scraper limit={scraper_limit}, llm model={llm_model}")
        return True
    except Exception as e:
        print(f"❌ Failed to load settings.yaml: {str(e)}")
        return False

def test_requirements_installation():
    """Test that key requirements can be imported."""
    tests = [
        ("yt-dlp", "yt_dlp"),
        ("google-api-python-client", "googleapiclient.discovery"),
        ("google-cloud-firestore", "google.cloud.firestore"), 
        ("agency-swarm", "agency_swarm"),
        ("openai", "openai"),
        ("pydantic", "pydantic"),
        ("pyyaml", "yaml")
    ]
    
    passed = 0
    for package_name, import_name in tests:
        try:
            __import__(import_name)
            print(f"✅ {package_name}: importable")
            passed += 1
        except ImportError:
            print(f"❌ {package_name}: not installed or not importable")
    
    success = passed == len(tests)
    if success:
        print(f"✅ All {len(tests)} required packages are importable")
    else:
        print(f"❌ {len(tests) - passed} packages failed import test")
    
    return success

def test_tool_env_loading():
    """Test that tools can load environment variables."""
    try:
        # Test ResolveChannelHandle tool
        from autopiloot.ScraperAgent.tools.ResolveChannelHandle import ResolveChannelHandle
        
        # Create tool instance (this should trigger env validation)
        tool = ResolveChannelHandle(channel_handle="@test")
        print("✅ ResolveChannelHandle tool can be instantiated")
        
        return True
    except Exception as e:
        print(f"❌ Tool environment loading failed: {str(e)}")
        return False

def create_sample_env_file():
    """Create a sample .env file for testing (with placeholder values)."""
    env_path = Path('/Users/maarten/Projects/16 - autopiloot/agents/.env.sample')
    
    sample_content = """# Sample .env file for testing (DO NOT use in production)
OPENAI_API_KEY=sk-test-key-placeholder
ASSEMBLYAI_API_KEY=test-assemblyai-key
YOUTUBE_API_KEY=test-youtube-key
SLACK_BOT_TOKEN=xoxb-test-token
GOOGLE_SERVICE_ACCOUNT_PATH=/path/to/test-service-account.json
GOOGLE_APPLICATION_CREDENTIALS=/path/to/test-service-account.json
GCP_PROJECT_ID=test-project-id
ZEP_API_KEY=test-zep-key
DRIVE_TRANSCRIPTS_FOLDER_ID=test-transcript-folder-id
DRIVE_SUMMARIES_FOLDER_ID=test-summaries-folder-id
SLACK_ALERTS_CHANNEL=test-alerts
TIMEZONE=Europe/Amsterdam
TRANSCRIPTION_DAILY_BUDGET_USD=5.0
BUDGET_ALERT_THRESHOLD=0.8
"""
    
    with open(env_path, 'w') as f:
        f.write(sample_content)
    
    print(f"✅ Created sample .env file at {env_path}")
    return True

def main():
    """Run all environment tests."""
    print("🧪 Testing Environment Configuration (TASK-ENV-0000)")
    print("=" * 60)
    
    tests = [
        ("Environment Template", test_env_template_exists),
        ("Environment Loader Import", test_env_loader_import),
        ("Settings YAML Access", test_settings_yaml_access),
        ("Requirements Installation", test_requirements_installation),
        ("Tool Environment Loading", test_tool_env_loading)
    ]
    
    passed_tests = 0
    total_tests = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🔍 Test: {test_name}")
        try:
            if test_func():
                passed_tests += 1
            else:
                print(f"   ⚠️  {test_name} failed")
        except Exception as e:
            print(f"   ❌ {test_name} error: {str(e)}")
    
    print(f"\n📊 Results: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests < total_tests:
        print("\n💡 To fix failing tests:")
        print("   1. Copy .env.template to .env and fill in real values")
        print("   2. Install requirements: pip install -r autopiloot/requirements.txt")
        print("   3. Ensure settings.yaml exists in autopiloot/config/")
        
        print(f"\n📝 Creating sample .env file for reference...")
        create_sample_env_file()
    
    return passed_tests == total_tests

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)