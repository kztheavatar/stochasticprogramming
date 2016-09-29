import cPickle
from gurobipy import *

### Read data from file you choose: commont/uncomment to choose the different files
### This file was generated from a separate python file, using the `cPickle' module
### This is just for convenience -- data can be read in many ways in Python

dfile = open('nd1041015.pdat','r')
#dfile = open('nd1510203000.pdat','r')

Fset = cPickle.load(dfile)  # set of facilities (list of strings)
Hset = cPickle.load(dfile)  # set of warehouses (list of strings)
Cset = cPickle.load(dfile)  # set of customers (list of strings)
Sset = cPickle.load(dfile)  # set of scenarios (list of strings)
arcExpCost = cPickle.load(dfile)  # arc expansion costs (dictionary mapping F,H and H,C pairs to floats)
facCap = cPickle.load(dfile)   # facility capacities (dictionary mapping F to floats)
curArcCap = cPickle.load(dfile)  # current arc capacities (dictionary mapping (i,j) to floats, where either
                                 # i is facility, j is warehouse, or i is warehouse and j is customer
unmetCost = cPickle.load(dfile)  # penalty for unment customer demands (dicationary mapping C to floats)
demScens = cPickle.load(dfile)  # demand scenarios (dictionary mapping (i,k) tuples to floats, where i is customer, k is
                                #scenario
dfile.close()

### Define sets of arcs (used as keys to dictionaries)
FHArcs = [(i,j) for i in Fset for j in Hset]  ## arcs from facilities to warehouses
HCArcs = [(i,j) for i in Hset for j in Cset]   ## arcs from warehouses to customers
AllArcs = FHArcs + HCArcs

### Make them Gurobi tuplelists
FHArcs = tuplelist(FHArcs)
HCArcs = tuplelist(HCArcs)
AllArcs = tuplelist(AllArcs)

num_scenes = len(Sset)
##### Start building the Model #####
master = Model("White Russian Company Master Problem")

### First stage vars, capacity increase decisions
capinc = {}
for arc in AllArcs:
    capinc[arc] = master.addVar(
        obj=float(arcExpCost[arc]),
        vtype=GRB.CONTINUOUS,
        name="CapacityIncrease_({0})".format(arc))

### Value Function Decision Variables
theta = {}
for s in Sset:
    theta[s] = master.addVar(
        vtype=GRB.CONTINUOUS,
        obj=1/(float(num_scenes)),
        name="Theta_{0}".format(s))

master.modelSense = GRB.MINIMIZE
master.update()

## Subproblem
sub = Model("White Russian Company Sub Problem")
sub.params.logtoconsole = 0

### Amount of extra units to buy to meet demand
unmet = {}
for c in Cset:
    unmet[c] = sub.addVar(
        vtype=GRB.CONTINUOUS,
        obj=float(unmetCost[c]),
        name="Unmet_{0}".format(c))

ship_on_arc = {}
for arc in AllArcs:
    ship_on_arc[arc] = sub.addVar(
        vtype=GRB.CONTINUOUS,
        obj=0,
        name="ShipOnArc_{0}".format(arc))

sub.modelSense = GRB.MINIMIZE
sub.update()

#### Arc Capacity Constraint Per Scenario####
arccapcon = {}
for arc in AllArcs:
    arccapcon[arc] = sub.addConstr(
        -ship_on_arc[arc] >= curArcCap[arc],
        name="ArcCapacity_{0}".format(arc))

#### Unit Flow Constraints ####
faccapcon = {}
for f in Fset:
    faccapcon[f] = sub.addConstr(
        -quicksum(ship_on_arc[f, h] for h in Hset) >= -facCap[f],
        name="FacilityCapacityConstr_{0}".format(f))

for h in Hset:
    sub.addConstr(
        quicksum(ship_on_arc[f, h] for f in Fset) - quicksum(ship_on_arc[h, c] for c in Cset) >= 0,
        name="HubCapacityConstr_{0}".format(h))

#### Demand Constraint ####
demcon = {}
for c in Cset:
    demcon[c] = sub.addConstr(
        unmet[c] + quicksum(ship_on_arc[h, c] for h in Hset) >=demScens[c, 'S0'],
        name="DemandConstr_{0}".format(c))

sub.update()

cuts = 1
iter = 1
while cuts > 0:

    print '================ Iteration ', iter, ' ==================='
    iter = iter + 1
    # solve master problem

    master.update()
    master.optimize()

    print "Lowerbound: {0}".format(master.objVal)

    cuts = 0
    upperbound = quicksum(arcExpCost[arc] * capinc[arc].x for arc in AllArcs)
    for s in Sset:
        # fix RHS in subproblem according to each scenario and master problem
        for arc in AllArcs:
            arccapcon[arc].RHS = -capinc[arc].x - curArcCap[arc]
        for c in Cset:
            demcon[c].RHS = demScens[c, s]

        sub.update()
        sub.optimize()
        upperbound += float(sub.objVal)/float(num_scenes)

        if sub.objVal > theta[s].x + 0.000001:
            facCapCoeff = {}
            for f in Fset:
                facCapCoeff[f] = -facCap[f] * faccapcon[f].Pi

            demandCoeff = {}
            for c in Cset:
                demandCoeff[c] = demScens[c, s] * demcon[c].Pi

            arccapCoeff = {}
            for arc in AllArcs:
                arccapCoeff[arc] = (-curArcCap[arc] - capinc[arc]) * arccapcon[arc].Pi

            master.addConstr(theta[s] >= (quicksum(arccapCoeff[arc] for arc in AllArcs) + quicksum(facCapCoeff[f] for f in Fset) + quicksum(demandCoeff[c] for c in Cset)))
            cuts += 1

    print "Upperbound: {0}".format(upperbound.getValue())
    print "Cuts found: {0}".format(cuts)

