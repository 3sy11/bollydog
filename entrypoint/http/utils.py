from authlib import jose


class JWT:
    def __init__(self, private, public):
        self.jwt = jose.jwt
        self.private = private
        self.public = public

    def encode(self, payload):
        return self.jwt.encode({'alg': 'RS256'}, payload, self.private).decode('utf-8')

    def decode(self, token):
        return self.jwt.decode(token, self.public)
