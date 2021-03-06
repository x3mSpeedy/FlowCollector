# encoding: utf-8
# author:   Jan Hybs
from perf.abstract import AbstractProcess


class MatrixCreate(AbstractProcess):
    """
    Test determining MEMORY performance
    Test complexity is not constant
    """

    def test(self, result):
        import numpy

        rnd = numpy.random.RandomState(1234)
        i = 0
        score = 0
        while not self.exit.is_set():
            rnd.random_sample((i + 1, i + 1))
            score = i
            i += 1
        result.value = score