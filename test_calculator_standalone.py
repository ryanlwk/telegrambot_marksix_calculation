"""
Standalone test cases for the calculator function logic.
This file contains the calculator function extracted for testing without dependencies.

Run with: uv run python test_calculator_standalone.py
"""


def calculator_logic(number1: float | None = None, 
                     number2: float | None = None, 
                     operation: str | None = None,
                     expression: str | None = None) -> float:
    """
    Calculator function logic (extracted from agent_setup.py for testing)
    """
    from simpleeval import simple_eval
    
    # If expression provided, use simpleeval for safe evaluation
    if expression:
        try:
            # Replace alternate operators with standard ones
            expression = expression.replace('×', '*').replace('÷', '/')
            result = simple_eval(expression.strip())
            return float(result)
        except Exception as e:
            raise ValueError(f"Cannot evaluate expression: {expression}. Error: {str(e)}")
    
    # Validate required parameters
    if number1 is None or number2 is None or operation is None:
        raise ValueError("Must provide either expression or (number1, number2, operation)")
    
    operation = operation.lower().strip()
    
    if operation in ['add', '+']:
        return number1 + number2
    elif operation in ['subtract', '-']:
        return number1 - number2
    elif operation in ['multiply', '*', '×', 'x']:
        return number1 * number2
    elif operation in ['divide', '/', '÷']:
        if number2 == 0:
            raise ValueError("Cannot divide by zero")
        return number1 / number2
    else:
        raise ValueError(f"Unsupported operation: {operation}")


# Test Suite
def run_tests():
    """Run all calculator tests"""
    print("="*60)
    print("CALCULATOR TOOL - TEST SUITE")
    print("="*60)
    print()
    
    passed = 0
    failed = 0
    tests = []
    
    # Test 1: Basic Addition with separate params
    tests.append({
        'name': 'Addition (separate params): 5 + 3',
        'call': lambda: calculator_logic(number1=5, number2=3, operation="add"),
        'expected': 8
    })
    
    tests.append({
        'name': 'Addition (operator symbol): 5 + 3',
        'call': lambda: calculator_logic(number1=5, number2=3, operation="+"),
        'expected': 8
    })
    
    # Test 2: Subtraction with separate params
    tests.append({
        'name': 'Subtraction: 10 - 3',
        'call': lambda: calculator_logic(number1=10, number2=3, operation="-"),
        'expected': 7
    })
    
    tests.append({
        'name': 'Subtraction (negative result): 1 - 9',
        'call': lambda: calculator_logic(number1=1, number2=9, operation="-"),
        'expected': -8
    })
    
    # Test 3: Multiplication
    tests.append({
        'name': 'Multiplication: 5 * 4',
        'call': lambda: calculator_logic(number1=5, number2=4, operation="*"),
        'expected': 20
    })
    
    tests.append({
        'name': 'Multiplication (× symbol): 5 × 4',
        'call': lambda: calculator_logic(number1=5, number2=4, operation="×"),
        'expected': 20
    })
    
    # Test 4: Division
    tests.append({
        'name': 'Division: 10 / 2',
        'call': lambda: calculator_logic(number1=10, number2=2, operation="/"),
        'expected': 5
    })
    
    tests.append({
        'name': 'Division (decimal result): 10 / 4',
        'call': lambda: calculator_logic(number1=10, number2=4, operation="/"),
        'expected': 2.5
    })
    
    # Test 5: Expression Parsing (THE KEY TESTS)
    tests.append({
        'name': 'Expression: "1-9" (THE BUG FIX)',
        'call': lambda: calculator_logic(expression="1-9"),
        'expected': -8
    })
    
    tests.append({
        'name': 'Expression: "5+3"',
        'call': lambda: calculator_logic(expression="5+3"),
        'expected': 8
    })
    
    tests.append({
        'name': 'Expression: "10*2"',
        'call': lambda: calculator_logic(expression="10*2"),
        'expected': 20
    })
    
    tests.append({
        'name': 'Expression: "8/4"',
        'call': lambda: calculator_logic(expression="8/4"),
        'expected': 2
    })
    
    # Test 6: Expression with spaces
    tests.append({
        'name': 'Expression with spaces: "5 + 3"',
        'call': lambda: calculator_logic(expression="5 + 3"),
        'expected': 8
    })
    
    tests.append({
        'name': 'Expression with spaces: "1 - 9"',
        'call': lambda: calculator_logic(expression="1 - 9"),
        'expected': -8
    })
    
    # Test 7: Decimals
    tests.append({
        'name': 'Decimals: 5.5 + 2.5',
        'call': lambda: calculator_logic(expression="5.5+2.5"),
        'expected': 8.0
    })
    
    tests.append({
        'name': 'Decimals: 7.5 / 2.5',
        'call': lambda: calculator_logic(expression="7.5/2.5"),
        'expected': 3.0
    })
    
    # Test 8: Negative numbers
    tests.append({
        'name': 'Negative number: -5 + 3',
        'call': lambda: calculator_logic(expression="-5+3"),
        'expected': -2
    })
    
    tests.append({
        'name': 'Negative number: -10 * 2',
        'call': lambda: calculator_logic(expression="-10*2"),
        'expected': -20
    })
    
    # Test 9: Alternate symbols
    tests.append({
        'name': 'Alternate symbol: 5 × 3',
        'call': lambda: calculator_logic(expression="5×3"),
        'expected': 15
    })
    
    tests.append({
        'name': 'Alternate symbol: 10 ÷ 2',
        'call': lambda: calculator_logic(expression="10÷2"),
        'expected': 5
    })
    
    # Test 10: Case insensitivity
    tests.append({
        'name': 'Case insensitive: ADD',
        'call': lambda: calculator_logic(number1=5, number2=3, operation="ADD"),
        'expected': 8
    })
    
    tests.append({
        'name': 'Case insensitive: Multiply',
        'call': lambda: calculator_logic(number1=5, number2=3, operation="Multiply"),
        'expected': 15
    })
    
    # Test 11: Real user scenarios from bug report
    tests.append({
        'name': 'User scenario: 1+1',
        'call': lambda: calculator_logic(expression="1+1"),
        'expected': 2
    })
    
    tests.append({
        'name': 'User scenario: 1+10',
        'call': lambda: calculator_logic(number1=1, number2=10, operation="+"),
        'expected': 11
    })
    
    tests.append({
        'name': 'User scenario: 1-9 (should be -8, not 10)',
        'call': lambda: calculator_logic(expression="1-9"),
        'expected': -8
    })
    
    # Test 12: Complex expressions (NEW with simpleeval)
    tests.append({
        'name': 'Complex: 1+2/3 (order of operations)',
        'call': lambda: calculator_logic(expression="1+2/3"),
        'expected': 1 + 2/3  # 1.6666...
    })
    
    tests.append({
        'name': 'Complex: (1+2)/3 (parentheses)',
        'call': lambda: calculator_logic(expression="(1+2)/3"),
        'expected': 1.0
    })
    
    tests.append({
        'name': 'Complex: 5*4+3',
        'call': lambda: calculator_logic(expression="5*4+3"),
        'expected': 23
    })
    
    tests.append({
        'name': 'Complex: 10-2*3',
        'call': lambda: calculator_logic(expression="10-2*3"),
        'expected': 4
    })
    
    tests.append({
        'name': 'Complex: 2**3 (power)',
        'call': lambda: calculator_logic(expression="2**3"),
        'expected': 8
    })
    
    tests.append({
        'name': 'Very complex: 2/4+3*5-1/2*7',
        'call': lambda: calculator_logic(expression="2/4+3*5-1/2*7"),
        'expected': 12.0
    })
    
    tests.append({
        'name': 'Complex with parentheses: (2+3)*(4-1)',
        'call': lambda: calculator_logic(expression="(2+3)*(4-1)"),
        'expected': 15.0
    })
    
    # Run all tests
    print("STANDARD TESTS:")
    print("-" * 60)
    for test in tests:
        try:
            result = test['call']()
            if result == test['expected']:
                print(f"✓ {test['name']}")
                print(f"  Result: {result}")
                passed += 1
            else:
                print(f"✗ {test['name']}")
                print(f"  Expected: {test['expected']}, Got: {result}")
                failed += 1
        except Exception as e:
            print(f"✗ {test['name']}")
            print(f"  Error: {e}")
            failed += 1
        print()
    
    # Error case tests
    print("ERROR HANDLING TESTS:")
    print("-" * 60)
    error_tests = []
    
    error_tests.append({
        'name': 'Division by zero',
        'call': lambda: calculator_logic(number1=10, number2=0, operation="/"),
        'expected_error': ValueError,
        'error_msg': 'Cannot divide by zero'
    })
    
    error_tests.append({
        'name': 'Invalid expression',
        'call': lambda: calculator_logic(expression="not math"),
        'expected_error': ValueError,
        'error_msg': 'Cannot evaluate expression'
    })
    
    error_tests.append({
        'name': 'Invalid operation',
        'call': lambda: calculator_logic(number1=5, number2=3, operation="power"),
        'expected_error': ValueError,
        'error_msg': 'Unsupported operation'
    })
    
    error_tests.append({
        'name': 'Missing parameters',
        'call': lambda: calculator_logic(),
        'expected_error': ValueError,
        'error_msg': 'Must provide either expression'
    })
    
    for test in error_tests:
        try:
            result = test['call']()
            print(f"✗ {test['name']}")
            print(f"  Expected error but got result: {result}")
            failed += 1
        except test['expected_error'] as e:
            if test['error_msg'] in str(e):
                print(f"✓ {test['name']}")
                print(f"  Correctly raised: {e}")
                passed += 1
            else:
                print(f"✗ {test['name']}")
                print(f"  Wrong error message: {e}")
                failed += 1
        except Exception as e:
            print(f"✗ {test['name']}")
            print(f"  Unexpected error: {e}")
            failed += 1
        print()
    
    # Summary
    print("="*60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*60)
    
    if failed == 0:
        print("✓ All tests passed!")
    else:
        print(f"✗ {failed} test(s) failed")
    
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
