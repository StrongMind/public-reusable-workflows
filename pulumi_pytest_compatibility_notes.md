
# 🛠️ Pulumi + Pytest Compatibility Notes

## Overview

As of **May 2025**, a subset of tests in this project began failing unexpectedly, even though **no code changes** were made. These failures were isolated to tests that used the `sut` fixture in combination with Pulumi’s `@pulumi.runtime.test` decorator.

After investigation, the root cause was identified as an indirect upgrade to **`pytest`**, triggered by changes in the **`pulumi`** Python package dependency behavior.

---

## ❗ The Problem

- The error observed:
  ```
  @pulumi.runtime.test
  E       fixture 'sut' not found
  ```
- Tests using `sut` began failing, despite working previously.
- The issue began **after May 16, 2025**, which coincides with recent upstream package updates.

---

## 📦 Packages Introducing Breaking Changes

### 1. **Pulumi v3.157.0** (Released March 2025)
- Added `pytest` and `pytest-watch` to its dependencies.
- This caused environments to **auto-upgrade pytest**, even if not explicitly listed in `requirements.txt`.
- **Issue:** [pulumi/pulumi#18965](https://github.com/pulumi/pulumi/issues/18965)

### 2. **Pytest v8.4.0** (Released June 2, 2025)
- Introduced **breaking changes** that made tests returning non-None (like `Output` values) or using async logic more fragile.
- Also introduced stricter fixture resolution behaviors.
- **Release notes:** [pytest-dev/pytest#release-8.4.0](https://docs.pytest.org/en/latest/changelog.html#pytest-8-4-0-2025-06-02)

---

## ✅ Recommended Fix

To avoid breakages, **pin** your dependencies to known-good versions that predate these changes.

Update your `requirements.txt` as follows:

```text
pulumi==3.156.0
pytest==8.3.5
pytest-watch==4.2.0
```

Then reinstall packages:

```bash
pip install --force-reinstall -r requirements.txt
```

This combination:
- Prevents Pulumi from auto-installing newer pytest versions.
- Uses a version of pytest that is compatible with Pulumi's `@pulumi.runtime.test`.
- Keeps fixture resolution behavior predictable and unchanged.

---

## 🧪 Additional Suggestions

If you must upgrade beyond these versions in the future:

1. **Avoid relying on `pytest` discovery for fixtures like `sut`** – consider importing explicitly.
2. **Update tests to return `None`** instead of returning assertions or Output directly.
3. **Use `pytest.mark.usefixtures()`** if you're relying on fixtures like `sut` in runtime-bound tests.
4. Consider adopting [`pytest-pulumi`](https://github.com/pulumi/pulumi-pytest) if and when it becomes stable, for more native integration.

---

## 🔗 References

- 🧪 Pytest 8.4.0 changelog:  
  https://docs.pytest.org/en/latest/changelog.html#pytest-8-4-0-2025-06-02

- 📦 Pulumi v3.157.0 issue:  
  https://github.com/pulumi/pulumi/issues/18965

- 🔍 Pulumi Releases:  
  https://github.com/pulumi/pulumi/releases

- 🧵 Related Discussion:  
  https://github.com/pulumi/pulumi/discussions/19337

---

## 🧭 Summary

| Package  | Version     | Reason |
|----------|-------------|--------|
| `pulumi` | `3.156.0`   | Last known version before pytest auto-installation |
| `pytest` | `8.3.5`     | Compatible with `@pulumi.runtime.test`, no fixture resolution changes |
| `pytest-watch` | `4.2.0` | Optional, but must match compatible pytest |

Lock these versions in your environment to ensure long-term test reliability.

---

# 🚀 Migration Plan for Future Dependency Updates

**⚠️ IMPORTANT**: This migration plan should be executed when you need to upgrade beyond the pinned versions above. The pinned versions are the immediate fix. This plan is for when you're ready to modernize the test suite for long-term compatibility.

## 📊 Current Test Suite Analysis

**Scope**: ~20 test files in `deployment/src/tests/`

**Current Patterns**:
- **sut fixtures**: Each test class defines its own `sut` (System Under Test) fixture
- **@pulumi.runtime.test**: Used extensively (hundreds of tests)
- **Return values**: Many tests return `Output.apply()` results from `assert_output_equals()`
- **Nested classes**: pytest-describe style organization

**Files Affected**: All test files using `@pulumi.runtime.test` decorator with `sut` fixtures

## 🎯 Migration Strategy: 3-Phase Approach

### Phase 1: Explicit Fixture Management 🔧
**Goal**: Remove dependency on automatic fixture discovery  
**Duration**: 2-3 days  
**Risk**: Low

#### Actions:
1. **Replace implicit fixture injection with explicit access**:

```python
# ❌ Current problematic pattern:
@pulumi.runtime.test
def it_has_a_name(sut):  # sut injected automatically
    return assert_output_equals(sut.execution_role.name, f"{sut.project_stack}-execution-role")

# ✅ New pattern:
@pulumi.runtime.test  
def it_has_a_name():
    sut = pytest.current_request().getfixturevalue('sut')  # Explicit fixture access
    return assert_output_equals(sut.execution_role.name, f"{sut.project_stack}-execution-role")
```

2. **Use `pytest.mark.usefixtures()` decorator**:

```python
@pytest.mark.usefixtures('sut')
class TestBatchComponent:
    @pulumi.runtime.test
    def it_exists(self):
        sut = pytest.current_request().getfixturevalue('sut')
        assert sut
```

#### Validation:
```bash
# Test with slightly newer pytest
pip install pytest==8.4.0 pulumi==3.156.0
python -m pytest deployment/src/tests/ -v
```

### Phase 2: Fix Return Value Issues ⚡
**Goal**: Eliminate tests returning non-None values  
**Duration**: 3-5 days  
**Risk**: Medium

#### Actions:
1. **Modify `shared.py` helper functions**:

```python
# ❌ Current implementation in shared.py:
def assert_output_equals(output, expected):
    def compare(value):
        try:
            assert value == expected
        except AssertionError:
            print(f"Expected: {expected}")
            print(f"Actual: {value}")
            raise
    return output.apply(compare)  # ❌ This returns a value

# ✅ New implementation:
def assert_output_equals(output, expected):
    def compare(value):
        try:
            assert value == expected
        except AssertionError:
            print(f"Expected: {expected}")
            print(f"Actual: {value}")
            raise
    
    # Force evaluation in test context rather than returning
    result = output.apply(compare)
    pulumi.runtime._sync_await(result)  # Forces the assertion to run
    # No return value
```

2. **Update all test methods**:

```python
# ❌ Current pattern:
@pulumi.runtime.test
def it_has_a_name(sut):
    return assert_output_equals(sut.execution_role.name, f"{sut.project_stack}-execution-role")

# ✅ New pattern:
@pulumi.runtime.test  
def it_has_a_name(sut):
    assert_output_equals(sut.execution_role.name, f"{sut.project_stack}-execution-role")
    # No return statement
```

#### Validation:
```bash
# Test with newer pytest
pip install pytest==8.4.0 pulumi==3.157.0
python -m pytest deployment/src/tests/ -v
```

### Phase 3: Modernize Test Structure 🏗️
**Goal**: Adopt robust patterns for long-term compatibility  
**Duration**: 5-7 days  
**Risk**: Low (optional optimization)

#### Actions:
1. **Flatten nested class structures**:

```python
# ❌ Current nested structure:
class TestBatchComponent:
    @pytest.fixture
    def sut(component_kwargs):
        return strongmind_deployment.batch.BatchComponent("batch-test", **component_kwargs)
    
    def describe_execution_role():
        @pulumi.runtime.test
        def it_has_a_name(sut):
            # test logic

# ✅ Flattened structure:
@pytest.fixture
def batch_sut(component_kwargs):
    return strongmind_deployment.batch.BatchComponent("batch-test", **component_kwargs)

@pulumi.runtime.test  
def test_batch_execution_role_has_correct_name(batch_sut):
    # test logic
```

2. **Centralize fixture definitions** in `conftest.py`:

```python
# In conftest.py:
@pytest.fixture
def component_kwargs():
    return {
        "project_stack": "test-stack", 
        "container_image": "test-image",
        # ... other common kwargs
    }

@pytest.fixture  
def batch_component(component_kwargs):
    return strongmind_deployment.batch.BatchComponent("batch-test", **component_kwargs)

@pytest.fixture
def lambda_component(lambda_args, lambda_env_variables):
    return strongmind_deployment.lambda_component.LambdaComponent("lambda-test", 
                                                                  args=lambda_args, 
                                                                  env_variables=lambda_env_variables)
```

## 📋 Implementation Checklist

### Phase 1 Tasks:
- [ ] **test_batch.py**: Update `sut` fixture access in all `@pulumi.runtime.test` methods
- [ ] **test_lambda.py**: Update `sut` fixture access in all `@pulumi.runtime.test` methods  
- [ ] **test_container.py**: Update `sut` fixture access in all `@pulumi.runtime.test` methods
- [ ] **test_dynamo.py**: Update `sut` fixture access in all `@pulumi.runtime.test` methods
- [ ] **test_redis.py**: Update `sut` fixture access in all `@pulumi.runtime.test` methods
- [ ] **Validate**: Test with `pytest==8.4.0 pulumi==3.156.0`

### Phase 2 Tasks:
- [ ] **shared.py**: Update `assert_output_equals()` to not return values
- [ ] **shared.py**: Update `assert_outputs_equal()` to not return values
- [ ] **All test files**: Remove `return` statements from `@pulumi.runtime.test` methods
- [ ] **All test files**: Ensure all tests use the updated assertion helpers
- [ ] **Validate**: Test with `pytest==8.4.0 pulumi==3.157.0`

### Phase 3 Tasks:
- [ ] **conftest.py**: Centralize common fixture definitions
- [ ] **test_batch.py**: Flatten nested class structure, rename fixtures
- [ ] **test_lambda.py**: Flatten nested class structure, rename fixtures
- [ ] **test_container.py**: Flatten nested class structure, rename fixtures
- [ ] **All test files**: Standardize test naming (`test_*` prefix)
- [ ] **Documentation**: Update team guidelines for new test patterns

## 🧪 Testing Strategy

### Pre-Migration Testing:
```bash
# Baseline test with current pinned versions
pip install pytest==8.3.5 pulumi==3.156.0 pytest-watch==4.2.0
python -m pytest deployment/src/tests/ -v --tb=short
```

### Phase-by-Phase Testing:
```bash
# After Phase 1
pip install pytest==8.4.0 pulumi==3.156.0
python -m pytest deployment/src/tests/ -v

# After Phase 2  
pip install pytest==8.4.0 pulumi==3.157.0
python -m pytest deployment/src/tests/ -v

# After Phase 3 (latest versions)
pip install pytest==8.5.0 pulumi==3.158.0  # or latest
python -m pytest deployment/src/tests/ -v
```

### CI/CD Integration:
```yaml
# Add to GitHub Actions
strategy:
  matrix:
    pytest-version: ["8.3.5", "8.4.0", "8.5.0"]
    pulumi-version: ["3.156.0", "3.157.0", "3.158.0"]
```

## ⚠️ Risk Mitigation

### Development Safety:
1. **Branch Strategy**: Create `migration/pytest-upgrade` branch for all changes
2. **Gradual Implementation**: Start with 1-2 test files, validate, then expand  
3. **Parallel Testing**: Keep both old and new test patterns during transition
4. **Rollback Plan**: Keep pinned versions as fallback in separate branch

### Testing Safety:
1. **Backup Current State**: Tag current working state before migration
2. **Isolated Testing**: Test each phase in isolation before combining
3. **Performance Monitoring**: Monitor test execution times for regressions
4. **Team Communication**: Notify team of migration timeline and potential impacts

## 📈 Success Metrics

### Phase 1 Success:
- [ ] All tests pass with `pytest==8.4.0`
- [ ] No fixture resolution errors
- [ ] Existing test behavior unchanged

### Phase 2 Success:
- [ ] All tests pass with `pytest==8.4.0 pulumi==3.157.0`
- [ ] No return value warnings or errors
- [ ] Assertion behavior unchanged

### Phase 3 Success:
- [ ] All tests pass with latest pytest/pulumi versions
- [ ] Improved test maintainability and clarity
- [ ] Centralized fixture management
- [ ] Team can easily add new tests following established patterns

## 🔄 Future Maintenance

### Dependency Management:
- Use `dependabot` or similar to monitor pytest/pulumi updates
- Test new versions in isolated environment before upgrading
- Maintain this migration plan document for future reference

### Team Guidelines:
1. **New Tests**: Must follow Phase 3 patterns (flattened structure, explicit fixtures)
2. **Fixture Naming**: Use descriptive names like `batch_component` instead of `sut`
3. **Return Values**: Never return values from `@pulumi.runtime.test` methods
4. **Documentation**: Update test patterns documentation after successful migration

## 📚 Additional Resources

- **pytest-pulumi**: Monitor [pytest-pulumi project](https://github.com/pulumi/pulumi-pytest) for official support
- **Pulumi Testing Guide**: [Official Pulumi testing documentation](https://www.pulumi.com/docs/using-pulumi/testing/)
- **pytest Documentation**: [Fixture documentation](https://docs.pytest.org/en/latest/reference/fixtures.html)

---

**Last Updated**: July 29 2025  
**Next Review**: After successful migration completion  
**Migration Status**: 🟡 Ready for Implementation (Phases 1-3 planned)
