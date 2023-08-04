from pulumi import Output


def assert_output_equals(output, expected):
    def compare(value):
        try:
            assert value == expected
        except AssertionError:
            print(f"Expected: {expected}")
            print(f"Actual: {value}")
            raise

    return output.apply(compare)


def assert_outputs_equal(expected_output, actual_output):
    def compare(args):
        expected, actual = args
        try:
            assert expected == actual
        except AssertionError:
            print(f"Expected: {expected}")
            print(f"Actual: {actual}")
            raise

    return Output.all(expected_output, actual_output).apply(compare)
