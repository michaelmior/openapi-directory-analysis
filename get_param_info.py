import io
import glob

import tqdm
import yaml


# See https://stackoverflow.com/a/37958106/123695
# This avoids converting strings to date objects since some are invalid
class NoDatesFullLoader(yaml.FullLoader):
    @classmethod
    def remove_implicit_resolver(cls, tag_to_remove):
        """
        Remove implicit resolvers for a particular tag

        Takes care not to modify resolvers in super classes.

        We want to load datetimes as strings, not dates, because we
        go on to serialise as json which doesn't have the advanced types
        of yaml, and leads to incompatibilities down the track.
        """
        if not "yaml_implicit_resolvers" in cls.__dict__:
            cls.yaml_implicit_resolvers = cls.yaml_implicit_resolvers.copy()

        for first_letter, mappings in cls.yaml_implicit_resolvers.items():
            cls.yaml_implicit_resolvers[first_letter] = [
                (tag, regexp) for tag, regexp in mappings if tag != tag_to_remove
            ]


NoDatesFullLoader.remove_implicit_resolver("tag:yaml.org,2002:timestamp")


# Parse invalid values as strings
# https://github.com/yaml/pyyaml/issues/89
def construct_value(load, node):
    if not isinstance(node, yaml.ScalarNode):
        raise yaml.constructor.ConstructorError(
            "while constructing a value",
            node.start_mark,
            "expected a scalar, but found %s" % node.id,
            node.start_mark,
        )
    yield str(node.value)


NoDatesFullLoader.add_constructor("tag:yaml.org,2002:value", construct_value)


for yaml_file in tqdm.tqdm(
    glob.glob("openapi-directory/APIs/**/*.yaml", recursive=True)
):
    with open(yaml_file) as file:
        try:
            # Strip non-printable characters
            yaml_str = yaml.reader.Reader.NON_PRINTABLE.sub("", file.read())

            # Wrap this in a StringIO object with the
            # appropriate name for better error messages
            yaml_io = io.StringIO(yaml_str)
            yaml_io.name = yaml_file

            data = yaml.load(yaml_io, Loader=NoDatesFullLoader)
        except yaml.scanner.ScannerError:
            # This can happen with embedded tabs in unquoted strings
            # https://github.com/yaml/pyyaml/issues/450
            continue
        except yaml.parser.ParserError:
            # Skip files which do not parse
            continue

        # Loop over all defined paths
        for path, methods in data.get("paths", {}).items():
            # Consider all possible methods
            for method, method_value in methods.items():
                # Ensure the values are lists
                method_values = method_value
                if not isinstance(method_values, list):
                    method_values = [method_values]

                for method_value in method_values:
                    # Skip cases where the method information is not a dictionary
                    if not isinstance(method_value, dict):
                        continue

                    # Print all path parameters
                    for param in method_value.get("parameters", []):
                        if param.get("in") == "path":
                            print(yaml_file, path, param["name"])
