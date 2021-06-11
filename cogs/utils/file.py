import toml

class File:
    def __init__(self, name):
        self.prefix = "data/"
        self.name = self.prefix + name

    def read(self):
        self.data = toml.load(self.name)
    
    def write(self, data):
        toml.dump(data, self.name)

    def read_addition(self, data):
        self.write(data)
        self.read()