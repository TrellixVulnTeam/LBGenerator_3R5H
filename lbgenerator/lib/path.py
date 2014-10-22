
class PathFunctions(object):

    def __init__(self, fn, args):
        if fn is None:
            self._callfn = getattr(self, '_standard')
        else:
            self._callfn = getattr(self, '_' + fn)
        assert isinstance(args, list)
        self._args = args

    def __call__(self, value):
        return self._callfn(value)

class InsertOnPathFunctions(PathFunctions):

    def _standard(self, match):
        return (True, self._args[0])

class UpdateOnPathFunctions(PathFunctions):

    def _standard(self, match):
        return (True, self._args[0])

    def _equals(self, match):
        if match.value == self._args[0]:
            return (True, self._args[1])
        return (False, None)

class DeleteOnPathFunctions(PathFunctions):

    def _standard(self, match):
        return True

    def _equals(self, match):
        if self._args[0] == match.value:
            return True
        return False

def get_path_fn(path, mode, fn=None, args=[]):
    """
    Path Operation Examples:
    {
        "path": "field",
        "mode": "insert",
        "fn": null,
        "args": ["875.637.971-49"]
    }
    """
    modefns ={
        'insert': InsertOnPathFunctions,
        'update': UpdateOnPathFunctions,
        'delete': DeleteOnPathFunctions}

    try:
        return path.split('/'), modefns[mode](fn, args)
    except KeyError:
        raise KeyError('Mode must be %s' % str(set(modes.keys())))


def parse_list_pattern(base, document, pattern):

    mapping ={
        'insert': base.set_path,
        'update': base.put_path,
        'delete': base.delete_path}

    for operation in pattern:
        path, fn = get_path_fn(**operation)
        method = mapping[operation['mode']]
        document = method(document, path, fn)

    return document
