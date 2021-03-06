# encoding: utf-8
# author:   Jan Hybs
import hashlib
from perf.abstract import AbstractProcess


class HashSHA(AbstractProcess):
    """
    Test determining CPU performance
    Test complexity is constant
    """

    def test(self, result):
        i = 0
        score = 0
        while not self.exit.is_set():
            hashlib.sha512('1234').hexdigest()
            score = i
            i += 1
        result.value = score