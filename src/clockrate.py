# encoding: utf-8
# author:   Jan Hybs

from optparse import OptionParser
import time
import re
import json
import platform
from subprocess import check_output

from perf.factorial import Factorial
from perf.forloop import ForLoop
from perf.hashsha import HashSHA
from perf.matrixcreate import MatrixCreate
from perf.matrixsolve import MatrixSolve
from perf.stringconcat import StringConcat
from utils.strings import human_readable


try:
    from psutil import cpu_count
except ImportError as e:
    from utils.simple_psutil import cpu_count
    print 'psutil lib missing, using simple_psutil cpu_count'

try:
    from psutil import virtual_memory
except ImportError as e:
    from utils.simple_psutil import virtual_memory
    print 'psutil lib missing, using simple_psutil virtual_memory'


try:
    from pluck import pluck
except ImportError as e:
    from utils.pluck import pluck
    print 'pluck lib missing, using local copy'

from utils.timer import Timer
from utils.progressbar import ProgressBar


timer = Timer()


class BenchmarkMeasurement(object):
    def __init__(self):
        self.timeout = .5
        self.tries = 3
        self.processes = 1

    def measure(self, cls, name, timeout=None, tries=None, processes=None):
        timeout = timeout if timeout is not None else self.timeout
        tries = tries if tries is not None else self.tries
        processes = processes if processes is not None else self.processes

        pb = ProgressBar(maximum=tries, width=30, prefix="{self.name:25}",
                         suffix=" {self.last_progress}/{self.maximum}")

        measure_result = list()
        for no_cpu in processes:
            pb.name = "{:s} {:d} {:s}".format(name, no_cpu, 'core' if no_cpu == 1 else 'cores')
            results = list()
            for i in range(0, tries):
                if print_output:
                    pb.progress(i)

                targets = [cls() for j in range(0, no_cpu)]

                with timer.measured("{:s} {:d}".format(name, i), False):
                    # start processes
                    for target in targets:
                        target.start()

                    # wait for timeout
                    time.sleep(timeout)

                    # send exit status
                    for target in targets:
                        target.shutdown()

                    # join threads
                    for target in targets:
                        target.join()

                tmp = dict()
                tmp['duration'] = timer.time()
                tmp['value'] = sum(pluck(targets, 'result.value'))
                tmp['exit'] = not max(pluck(targets, 'terminated'))
                results.append(tmp)

            if print_output:
                pb.end()

            result = dict()
            result['processes'] = no_cpu
            result['exit'] = min(pluck(results, 'exit'))
            result['duration'] = sum(pluck(results, 'duration')) / float(tries)
            result['value'] = sum(pluck(results, 'value')) / float(tries)
            result['performance'] = result['value'] / result['duration']


            if human_format:
                result['value'] = human_readable(result['value'])
                result['performance'] = human_readable(result['performance'])

            measure_result.append(result)

        return measure_result


    def configure(self, timeout, tries, processes):
        self.timeout = timeout
        self.tries = tries
        self.processes = processes if type(processes) is list else [processes]


print_output = True
human_format = False
all_tests = set(['for-loop', 'factorial', 'hash-sha', 'matrix-creation', 'matrix-solve', 'string-concat'])


def create_parser():
    """Creates command line parse"""
    parser = OptionParser()

    parser.add_option("-i", "--include", dest="includes", metavar="TESTNAME", default=[], action="append",
                      help="Turn on specific perf, by default all perf are included")
    parser.add_option("-x", "--exclude", dest="excludes", metavar="TESTNAME", default=[], action="append",
                      help="Turn off specific perf")
    parser.add_option("-c", "--core", dest="cores", metavar="CORE", default=[], action="append",
                      help="Try test with this amount of core, by default 1...N, where N is maximum cores available")

    parser.add_option("-d", "--duration", dest="timeout", metavar="DURATION", default=0.4,
                      help="Maximum duration per one test case")
    parser.add_option("-t", "--tries", dest="tries", metavar="TRIES", default=2,
                      help="Number of tries for each test")
    parser.add_option("-q", "--quiet", dest="quiet", default=True, action="store_false",
                      help="Do not print any output")
    parser.add_option("-H", "--human", dest="human", default=False, action="store_true",
                      help="Output in human-readable format")

    parser.set_usage("""%prog [options]""")
    return parser


def parse_args(parser):
    global print_output, human_format

    """Parses argument using given parses and check resulting value combination"""
    (options, args) = parser.parse_args()

    includes = set(options.includes) if options.includes else all_tests.copy()
    if options.excludes:
        includes = includes - set(options.excludes)

    if not options.cores:
        options.cores = range(1, cpu_count(logical=True) + 1)
    else:
        options.cores = [int(value) for value in options.cores]

    if options.human:
        human_format = True

    options.tries = int(options.tries)
    options.timeout = float(options.timeout)
    print_output = options.quiet

    assert options.tries > 0, 'Number of tries must be positive integer'
    assert options.timeout > 0, 'Timeout value must be positive number'

    return options, args, includes


def main():
    parser = create_parser()
    (options, args, includes) = parse_args(parser)

    try:
        # with timer.measured('node-performance', print_output):
            if print_output:
                print "{:-^55}".format("Running perf")
                print "{:-^55}".format(str(includes))

            measurement = BenchmarkMeasurement()
            measurement.configure(options.timeout, options.tries, options.cores)

            test_results = dict()
            if 'for-loop' in includes:
                test_results['for-loop'] = measurement.measure(ForLoop, 'For loop')

            if 'factorial' in includes:
                test_results['factorial'] = measurement.measure(Factorial, 'Factorial')

            if 'hash-sha' in includes:
                test_results['hash-sha'] = measurement.measure(HashSHA, 'Hash')

            if 'matrix-creation' in includes:
                test_results['matrix-creation'] = measurement.measure(MatrixCreate, 'Matrix create')

            if 'matrix-solve' in includes:
                test_results['matrix-solve'] = measurement.measure(MatrixSolve, 'Matrix solve')

            if 'string-concat' in includes:
                test_results['string-concat'] = measurement.measure(StringConcat, 'String concat')

            if print_output:
                print "\n{:-^55}".format("Getting node info")

            info = dict()
            info['memory'] = dict()
            info['memory']['total'] = virtual_memory().total
            info['memory']['avail'] = virtual_memory().available

            # info['disk'] = [psutil.disk_partitions()]
            info['cpu'] = dict()
            info['cpu']['physical'] = cpu_count(logical=False)
            info['cpu']['logical'] = cpu_count(logical=True)
            info['cpu']['architecture'] = platform.processor()
            if platform.system() == 'Linux':
                cpu_info = check_output('cat /proc/cpuinfo', shell=True).split('\n')
                for line in cpu_info:
                    if "model name" in line:
                        info['cpu']['name'] = re.sub(".*model name.*:", "", line, 1).strip()
                    if "cpu MHz" in line:
                        info['cpu']['frequency'] = float(re.sub(".*cpu MHz.*:", "", line, 1).strip())


            elif platform.system() == 'Windows':
                cpu_freq = check_output('wmic cpu get MaxClockSpeed', shell=True)
                cpu_freq = cpu_freq.replace('\n', '').replace('MaxClockSpeed', '').strip()
                info['cpu']['frequency'] = int(cpu_freq)

                cpu_name = check_output('wmic cpu get Caption', shell=True)
                cpu_name = cpu_name.replace('\n', '').replace('Caption', '').strip()
                info['cpu']['name'] = cpu_name

            info['system'] = dict()
            info['system']['platform'] = platform.system()
            info['system']['processor'] = platform.processor()
            info['system']['version'] = platform.version()
            info['system']['machine'] = platform.machine()
            info['system']['node'] = platform.node()
            info['system']['release'] = platform.release()

            clockrate_result = { 'architecture': info, 'perf': test_results }

            try:
                with open('node_test.json', 'w+') as fp:
                    json.dump(clockrate_result, fp, indent=4, sort_keys=True)
            except Exception as er:
                print 'Error while saving file'
                raise er

            if print_output:
                try:
                    with open('node_test.json', 'r+') as fp:
                        print fp.read()
                except Exception as er:
                    print 'Error while reading file'
                    raise er

            if print_output:
                print "\n{:-^55}".format("Benchmark test finished")

    except Exception as e:
        print e
        raise e


if __name__ == '__main__':
    main()