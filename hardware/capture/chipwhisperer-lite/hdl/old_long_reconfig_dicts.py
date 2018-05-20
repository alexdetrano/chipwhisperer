# Copyright Colin O'Flynn 2013-2015
# www.NewAE.com
#
# This generates one batch of PR data. Called by parallel_generate.py
# to run a bunch of these in parallel.
#
# At some point: need to try calling fpga_editor once, with a larger
#                script that writes a bunch of temporary .ncd files.
#                This might be faster then each time fpga_editor loading
#                all the data.
#

from subprocess import call
import os
import pickle
import sys

#Windows Path
#XILINX_DIR = "C:\\Xilinx\\14.4\\ISE_DS\\ISE\\bin\\nt64\\"
#DESIGN_BASE = "cwlite_ise\\cwlite_interface"

#Linux Path
XILINX_DIR = "/opt/Xilinx/14.7/ISE_DS/ISE/bin/lin64/"
#DESIGN_BASE = "cwlite_ise/cwlite_interface"

def cleanup():
    dellist = ["diffbits.rbt", "diffscr.scr", "diff.pcf", "diff.ncd",
               "diffbits.bgn", "diffbits.bit", "diffbits.drc", "diffbits.ll", "diffbits_bitgen.xwbt",
               "usage_statistics_webtalk.html", "webtalk.log", "xilinx_device_details.xml",
               "diffscr.scr", "reversebits.bit", "reversebits.drc", "reversebits.bgn",
               "reversebits.rbt", "reversebits_bitgen.xwbt",
               ]
    

    for f in dellist:
        try:
            os.remove(f)
        except OSError, e:
            pass

    
def makeDiffBits_phase(phases, comps, DESIGN_BASE, cfgString = "CLKDV_DIVIDE:2.0 CLKIN_DIVIDE_BY_2:FALSE CLKOUT_PHASE_SHIFT:VARIABLE CLK_FEEDBACK:2X DESKEW_ADJUST:5 DFS_FREQUENCY_MODE:LOW DLL_FREQUENCY_MODE:LOW DSS_MODE:NONE DUTY_CYCLE_CORRECTION:TRUE PSCLKINV:PSCLK PSENINV:PSEN PSINCDECINV:PSINCDEC RSTINV:RST STARTUP_WAIT:FALSE VERY_HIGH_FREQUENCY:FALSE", reverse=False):
    script = "post attr main\n"
    script += "setattr main edit-mode Read-Write\n"
    script += "setattr main case_sensitive off\n"
    for i,comp in enumerate(comps):
	    ATTR_PHASE = phases[i]
	    script += "unselect -all\n"
	    script += "select comp '%s'\n"%comp
	    script += "post block\n"
	    script += 'setattr comp %s PHASE_SHIFT "%d"\n'%(comp, ATTR_PHASE)
	    script += 'setattr comp %s Config "%s"\n'%(comp, cfgString)
	    script += "block apply\n"
	    script += "end block\n"
    script += 'save -w design "diff.ncd" "diff.pcf"\n'
    script += "exit\n"
    script += "end\n"

    f = open("diffscr.scr", "w")
    f.write(script)
    f.close()
    
    call([XILINX_DIR + "fpga_edline", DESIGN_BASE+".ncd", DESIGN_BASE+".pcf", "-p", "diffscr"])

    if reverse:
        call([XILINX_DIR + "bitgen", "-g", "ActiveReconfig:Yes", "diff.ncd", "diffbits.bit", "-w", "-d"])
        call([XILINX_DIR + "bitgen", "-g", "ActiveReconfig:Yes", "-r", "diffbits.bit", "-w", "-d", DESIGN_BASE+".ncd", "reversebits.bit", "-b"])
    else:
        call([XILINX_DIR + "bitgen", "-g", "ActiveReconfig:Yes", "-r", DESIGN_BASE+".bit", "-w", "-d", "diff.ncd", "diffbits.bit", "-b", "-l"])

def parseRbt(bgtname="diffbits.rbt"):
    f = open(bgtname, "r")

    bitsnow = False

    data = []

    for line in f:
        if bitsnow:
            data.append(int(line, 2))
        elif "Part" in line:
            part = line.split()[1]
        elif "1111111111111111" in line:
            data.append(int(line, 2))
            bitsnow = True

    return (part, data)

def updateDict(d, parsed, param, descstr="", locationstr=""):
    try:
        d["part"]
    except KeyError:
        d["part"] = parsed[0]
        d["crc32"] = 0
        d["desc"] = descstr
        d["location"] = locationstr
        d["base"] = parsed[1]
        d["values"] = {}

    if d["part"] != parsed[0]:
        raise ValueError("INVALID PART!?")

    if param is not None:
        d["values"][param] = []
        for idx, val in enumerate(parsed[1]):
            try:
                if val != d["base"][idx]:
                    d["values"][param].append( (idx, val) )
            except IndexError, e:
                print("Number of changes differs from 'base'! Make sure phase range starts at non-default")
                print("And reference bitfile was generated by same version of tools as being called here")
                print("otherwise regenerate reference bitfile from .ncd file")
                raise IndexError(e)
    
def generateAllDiffs(comp, desc, filename, values1, values2, DESIGN_BASE):  
    saveDict = {}
    cleanup()

    #This inits the "base" reference bitfile, which is the partial reconfig bitstream required
    #to bring system BACK to normal state. This MUST be the base state, otherwise the system
    #will never record the required changes to bring the FPGA back to initial state
    makeDiffBits_phase([-1, -1], comp, DESIGN_BASE, reverse=True)
    p = parseRbt("reversebits.rbt")
    updateDict(saveDict, p, None, desc, comp)   

    for w in values2:
        for o in values1:
            cleanup()
            print("Offset = %d, Width=%d"%(o, w))
            makeDiffBits_phase([o, w], comp, DESIGN_BASE)
            p = parseRbt()
            updateDict(saveDict, p, (o,w), desc, comp)
            pickle.dump(saveDict, open(filename, 'wb'))
    #cleanup()
    pickle.dump(saveDict, open(filename, 'wb'))

if len(sys.argv) != 3:
    print("Usage: %s design_base width"%sys.argv[0])
    print("i.e.: %s 'cwlite_ise/cwlite_interface' 10"%sys.argv[0])
else:
    generateAllDiffs(["reg_clockglitch/gc/DCM_extclock_gen", "reg_clockglitch/gc/DCM_extclock_gen2"], "Glitch Offset/Width", "cwlite-glitchoffsetwidth.p", range(-127, 127), [int(sys.argv[2])], sys.argv[1])



