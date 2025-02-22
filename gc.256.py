#!/usr/bin/env python

import os, sys
import pycuda.driver as cuda
import pycuda.autoinit
from pycuda.autoinit import context
from pycuda.compiler import SourceModule
import math

class SHAgpu:

    cuda_inited = False
    threadMax = 1024
    blockMax = 1024
    cuda_buf_size =  threadMax

    def __init__(self,
        alphabet='abcdefghijklmnopqrstuvwxyzABCDEF', length=6, set_bits=26, set_bits_val=1,
        threadMax = 1024, blockMax = 1024):
        self.threadMax = threadMax
        self.blockMax = blockMax
        self.alphabet = alphabet
        self.alphalen = len(self.alphabet)
        self.length = length
        self.loglen = int(math.log(len(self.alphabet)) / math.log(2))
        self.set_bits = set_bits
        self.set_bits_val = set_bits_val

    def hex_encode(self, str):
        return ''.join(hex(ord(c)) + ',' for c in str)[:-1]

    def generate_mask_function(self):
        full = self.set_bits / 8
        rem = self.set_bits % 8
        L = ['(buf[' + str(31-i) + '] == 0xff)' for i in range(0, full)]
        R = ['(buf[' + str(31-full) + '] == ' + hex(2**rem - 1) + ')']
        return '&&'.join(L + R)

    def inv_generate_mask_function(self):
        full = self.set_bits / 8
        rem = self.set_bits % 8
        L = ['(buf[' + str(31-i) + '] != 0xff)' for i in range(0, full)]
        R = ['(buf[' + str(31-full) + '] != ' + hex(2**rem - 1) + ')']
        return '||'.join(L + R)

    def init_cuda(self, prefix):
        if self.cuda_inited:
            return

        f = open('gc.sha256.c')
        cuda_kernel = f.read()
        cuda_kernel = cuda_kernel.replace('__MAX_ITERATIONS__',
                    str(len(self.alphabet) ** self.length))
        cuda_kernel = cuda_kernel.replace('__ALPHABET__',
                    self.hex_encode(self.alphabet))
        cuda_kernel = cuda_kernel.replace('__LENGTH__', str(self.length))
        cuda_kernel = cuda_kernel.replace('__LOG2ALPHABET__', str(self.loglen))
        cuda_kernel = cuda_kernel.replace('__MASK__', str(self.alphalen - 1))
        cuda_kernel = cuda_kernel.replace('__PREFIX__',
                    self.hex_encode(prefix + '\x00' * (self.length + 1)))
        cuda_kernel = cuda_kernel.replace('__PREFIXLEN__', str(len(prefix)))
        cuda_kernel = cuda_kernel.replace('__MASKFUNC__', self.generate_mask_function())
        cuda_kernel = cuda_kernel.replace('__INVMASKFUNC__', self.inv_generate_mask_function())
        f.close()
        f = open('gc.sha256.cu',"w+")
        f.write(cuda_kernel)
        f.close()

        self.mod = SourceModule(cuda_kernel,options=['--maxrregcount=63'])
        self.cuda_buf = cuda.mem_alloc(self.cuda_buf_size)
        self.cuda_inited = True


    def cuda_run(self, prefix, silent):
        if not silent:
                print 'Running grocollv256 on 2^%s candidates...' % str(self.loglen * self.length)
                print '-' * 30
        self.init_cuda(prefix)
        run = self.mod.get_function("run");
        print(run.num_regs)
        run(block = (1024, 1, 1), grid = (256, 1))
        context.synchronize()

if __name__ == "__main__":
    silent = False
    if len(sys.argv) == 1:
        prefix = 'grocid'
    if len(sys.argv) == 2:
        prefix = sys.argv[1]
    if len(sys.argv) == 3:
        prefix = sys.argv[1]
        if sys.argv[2] == '-s':
            silent = True

    hasher = SHAgpu()
    hasher.cuda_run(prefix, silent)
