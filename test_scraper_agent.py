"""
Test script for ScraperAgent instantiation and basic functionality.
"""

import sys
import os
sys.path.append('/Users/maarten/Projects/16 - autopiloot/agents')

from autopiloot.ScraperAgent.ScraperAgent import ScraperAgent

def test_agent_instantiation():
    """Test that ScraperAgent can be instantiated without errors."""
    try:
        print("Creating ScraperAgent...")
        agent = ScraperAgent()
        print(f"✅ Agent created successfully!")
        print(f"   Name: {agent.name}")
        print(f"   Description: {agent.description}")
        print(f"   Model: {agent.model}")
        print(f"   Temperature: {agent.temperature}")
        print(f"   Tools loaded: {len(agent.tools) if hasattr(agent, 'tools') else 'Unknown'}")
        
        return agent
        
    except Exception as e:
        print(f"❌ Failed to create agent: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def test_tool_access():
    """Test that tools are accessible from the agent."""
    try:
        agent = ScraperAgent()
        
        # Check if tools are loaded
        if hasattr(agent, 'tools') and agent.tools:
            print(f"✅ Tools loaded: {list(agent.tools.keys())}")
        else:
            print("⚠️  No tools detected or tools not loaded yet")
            
        return True
        
    except Exception as e:
        print(f"❌ Tool access test failed: {str(e)}")
        return False

if __name__ == "__main__":
    print("🧪 Testing ScraperAgent...")
    print("=" * 50)
    
    # Test 1: Basic instantiation
    print("Test 1: Agent Instantiation")
    agent = test_agent_instantiation()
    print()
    
    # Test 2: Tool access
    if agent:
        print("Test 2: Tool Access")
        test_tool_access()
        print()
    
    print("🏁 Test completed!")