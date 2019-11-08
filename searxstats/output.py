from _ctypes import PyObj_FromPtr
import json
import re


class NoIndent:
    """ Value wrapper. """

    def __init__(self, value):
        self.value = value


# see https://stackoverflow.com/questions/16264515/json-dumps-custom-formatting
class MyEncoder(json.JSONEncoder):
    FORMAT_SPEC = '@@{}@@'
    regex = re.compile(FORMAT_SPEC.format(r'(\d+)'))

    def __init__(self, **kwargs):
        # Save copy of any keyword argument values needed for use here.
        self.__sort_keys = kwargs.get('sort_keys', None)
        super(MyEncoder, self).__init__(**kwargs)

    # see https://github.com/PyCQA/pylint/pull/3206
    def default(self, o): # pylint: disable=E0202
        return (self.FORMAT_SPEC.format(id(o)) if isinstance(o, NoIndent)
                else super(MyEncoder, self).default(o))

    def encode(self, o):
        format_spec = self.FORMAT_SPEC  # Local var to expedite access.
        json_repr = super(MyEncoder, self).encode(o)  # Default JSON.

        # Replace any marked-up object ids in the JSON repr with the
        # value returned from the json.dumps() of the corresponding
        # wrapped Python object.
        for match in self.regex.finditer(json_repr):
            # see https://stackoverflow.com/a/15012814/355230
            py_ptr = int(match.group(1))
            no_indent = PyObj_FromPtr(py_ptr)
            json_obj_repr = json.dumps(no_indent.value, sort_keys=self.__sort_keys)

            # Replace the matched id string with json formatted representation
            # of the corresponding Python object.
            json_repr = json_repr.replace(
                '"{}"'.format(format_spec.format(py_ptr)), json_obj_repr)

        return json_repr


if __name__ == '__main__':
    from string import ascii_lowercase as letters

    DATA = {
        'layer1': {
            'layer2': {
                'layer3_1': NoIndent([{"x": 1, "y": 7}, {"x": 0, "y": 4}, {"x": 5, "y": 3},
                                      {"x": 6, "y": 9},
                                      {k: v for v, k in enumerate(letters)}]),
                'layer3_2': 'string',
                'layer3_3': NoIndent([{"x": 2, "y": 8, "z": 3}, {"x": 1, "y": 5, "z": 4},
                                      {"x": 6, "y": 9, "z": 8}]),
                'layer3_4': NoIndent(list(range(20))),
            }
        }
    }

    print(json.dumps(DATA, cls=MyEncoder, sort_keys=True, indent=2))
