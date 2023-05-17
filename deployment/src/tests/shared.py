from pulumi import Output


def assert_output_equals(output, expected):
    def compare(value):
        assert value == expected

    return output.apply(compare)


def assert_outputs_equal(expected_output, actual_output):
    def compare(args):
        expected, actual = args
        assert expected == actual

    return Output.all(expected_output, actual_output).apply(compare)
