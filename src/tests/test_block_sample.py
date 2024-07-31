import os

var = 100


def test():
    def test_inner():
        pass


class A(object):
    def __init__(self) -> None:
        pass

    def run(self):
        def xxxx():
            pass

        xxxx()


var = 200


def vvv():
    pass


async def vvv():
    pass


class B(object):
    def __call__(self, *args: os.Any, **kwds: os.Any) -> os.Any:
        pass

    async def run(self, config, options):
        pass


if __name__ == "__main__":
    pass
