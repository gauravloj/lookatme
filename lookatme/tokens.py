tokentypes = {"marker", "attrs", "children", "bullet", "tight", "style", "raw", "type"}


def get_token_types(self, tokens):
    """Get the token types from the provided tokens

    :param list tokens: The tokens to get types for
    :returns: list of token types
    """
    types = []
    if "children" in tokens:
        for child in tokens["children"]:
            types.extend(self.get_token_types(child))
    else:
        types.append(tokens["type"])
    return types


def get_token_types(self, tokens):
    alltokens = []
    for token in tokens:
        alltokens.extend(token)
