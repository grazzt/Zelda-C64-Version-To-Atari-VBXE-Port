"""Build a variant of the kit's generated 6502 core that records the address of the executing instruction
in `self.ipc` (needed to attribute every VIC/SID/CIA/EF access to a code address)."""
import sys, os
_REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))  # the repo root
_KIT = os.environ.get('PORTKIT') or os.path.join(os.path.dirname(_REPO), 'port_kit')  # the port kit
sys.path.insert(0, _KIT + '/tools/c64')
import mos6502
from itertools import repeat

def traced_cpu_class():
    src = mos6502._source(False).replace("        op = mem[pc]\n", "        op = mem[pc]\n        self.ipc = pc\n")
    ns = {'repeat': repeat, 'CPUError': mos6502.CPUError}
    exec(compile(src, '<traced 6502 core>', 'exec'), ns)
    class TCPU(mos6502.CPU):
        ipc = 0
        def __init__(self, mem, coverage=False):
            super().__init__(mem, False)
            self._run = ns['run']
    return TCPU
