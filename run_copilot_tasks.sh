#!/bin/bash
# Sherlock Copilot Task Execution Script
# Runs: install, verify, and search operations

set -e

echo "🚀 Sherlock Copilot Task Execution"
echo "===================================="
echo ""

# Step 1: Install
echo "📦 Step 1: Installing Sherlock..."
echo "Command: python3 copilot_task.py install"
echo ""
python3 copilot_task.py install
INSTALL_RESULT=$?

if [ $INSTALL_RESULT -ne 0 ]; then
    echo "❌ Installation failed. Exiting."
    exit 1
fi

echo ""
echo "-----------------------------------"
echo ""

# Step 2: Verify
echo "🧪 Step 2: Verifying Installation..."
echo "Command: python3 copilot_task.py verify"
echo ""
python3 copilot_task.py verify
VERIFY_RESULT=$?

if [ $VERIFY_RESULT -ne 0 ]; then
    echo "❌ Verification failed. Exiting."
    exit 1
fi

echo ""
echo "-----------------------------------"
echo ""

# Step 3: Search
echo "🔍 Step 3: Searching for 'testuser'..."
echo "Command: python3 copilot_task.py search testuser"
echo ""
python3 copilot_task.py search testuser
SEARCH_RESULT=$?

echo ""
echo "-----------------------------------"
echo ""

# Summary
echo "✅ Execution Complete!"
echo ""
echo "Results Summary:"
echo "  Install:  $([ $INSTALL_RESULT -eq 0 ] && echo '✅ Success' || echo '❌ Failed')"
echo "  Verify:   $([ $VERIFY_RESULT -eq 0 ] && echo '✅ Success' || echo '❌ Failed')"
echo "  Search:   $([ $SEARCH_RESULT -eq 0 ] && echo '✅ Success' || echo '❌ Failed')"
echo ""

if [ -f "testuser.txt" ]; then
    echo "📄 Results saved to: testuser.txt"
    echo "First 10 lines of results:"
    head -n 10 testuser.txt
    echo ""
fi

echo "🎉 Ready to use Sherlock!"
echo ""
echo "Next steps:"
echo "  • python3 copilot_task.py search alice bob --csv"
echo "  • python3 copilot_task.py test"
echo "  • sherlock --help"
