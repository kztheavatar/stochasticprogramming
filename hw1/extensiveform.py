import cPickle
from gurobipy import *
import sys

debug=False

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

############################
##### STOCHASTIC MODEL #####
############################

m = Model("White Russian Company")

### First stage vars, capacity increase decisions
capinc = {}
for arc in AllArcs:
    capinc[arc] = m.addVar(
        obj=float(arcExpCost[arc]),
        name="CapacityIncrease_({0})".format(arc))

### Second stage vars, amount of extra units to buy to meet demand
unmet = {}
num_scenes = len(Sset)
for c in Cset:
    for s in Sset:
        unmet[c, s] = m.addVar(
            obj=float(unmetCost[c])/num_scenes,
            name="Unmet_({0}, {0})".format(c, s))

ship_on_arc = {}
for arc in AllArcs:
    for s in Sset:
        ship_on_arc[arc, s] = m.addVar(
            obj=0,
            name="ShipOnArc_{0}_scenario_{1}".format(arc, s))

m.modelSense = GRB.MINIMIZE
m.update()

#### Arc Capacity Constraint Per Scenario####
for s in Sset:
    for arc in AllArcs:
        m.addConstr(
            curArcCap[arc] + capinc[arc] >= ship_on_arc[arc, s],
            name="ArcCapacity_{0}_in_scenario_{1}".format(arc, s))

#### Unit Flow Constraints ####
for f in Fset:
    for s in Sset:
        m.addConstr(
            quicksum(ship_on_arc[(f, h), s] for h in Hset) <= facCap[f],
            name="FacilityCapacityConstr_{0}_scenario_{1}".format(f, s))

for h in Hset:
    for s in Sset:
        m.addConstr(
            quicksum(ship_on_arc[(h, c), s] for c in Cset) <= quicksum(ship_on_arc[(f, h), s] for f in Fset),
            name="HubCapacityConstr_{0}_scenario_{1}".format(h, s))

#### Demand Constraint ####
for c in Cset:
    for s in Sset:
        m.addConstr(
            unmet[c, s] + quicksum(ship_on_arc[(h, c), s] for h in Hset) >= demScens[c, s],
            name="DemandConstr_{0}_scenario_{1}".format(c, s))

m.update()
m.optimize()
if m.status == GRB.Status.OPTIMAL:
    exp_cost_stochastic = m.objVal
    print "OBJECTIVE VALUE: {0}".format(exp_cost_stochastic)

    if debug:
        print "SOLUTION:"
        for arc in AllArcs:
            if capinc[arc].x > 0.00001:
                print "Capacity for {0} increased by {1}".format(arc, capinc[arc].x)
        print("AVERAGE UNMET DEMAND:")
        for c in Cset:
            avgunmet = quicksum(unmet[c, s].x for s in Sset)/num_scenes
            print("Customer {0}: {1}".format(c, avgunmet))

    print("RUNTIME: {0}".format(m.Runtime))
else:
    print("Extensive Form probem is infeasible")
    sys.exit(1)

###############################
##### Mean Value Problem ######
###############################

mvm = Model("Average White Russian Comapny")
### First stage vars, capacity increase decisions
mvm_capinc = {}
for arc in AllArcs:
    mvm_capinc[arc] = mvm.addVar(
        obj=arcExpCost[arc],
        name="CapacityIncrease_({0})".format(arc))

### Second stage vars, amount of extra units to buy to meet demand
mvm_unmet = {}
for c in Cset:
    for s in Sset:
        mvm_unmet[c, s] = mvm.addVar(
            obj=float(unmetCost[c]),
            name="Unmet_({0}, {0})".format(c, s))

mvm_ship_on_arc = {}
for arc in AllArcs:
    for s in Sset:
        mvm_ship_on_arc[arc, s] = mvm.addVar(
            obj=0,
            name="ShipOnArc_{0}_scenario_{1}".format(arc, s))

mvm.modelSense = GRB.MINIMIZE
mvm.update()

#### Arc Capacity Constraint Per Scenario####
for s in Sset:
    for arc in AllArcs:
        mvm.addConstr(
            curArcCap[arc] + mvm_capinc[arc] >= mvm_ship_on_arc[arc, s],
            name="ArcCapacity_{0}_in_scenario_{1}".format(arc, s))

#### Unit Flow Constraints ####
for f in Fset:
    for s in Sset:
        mvm.addConstr(
            quicksum(mvm_ship_on_arc[(f, h), s] for h in Hset) <= facCap[f],
            name="FacilityCapacityConstr_{0}_scenario_{1}".format(f, s))

for h in Hset:
    for s in Sset:
        mvm.addConstr(
            quicksum(mvm_ship_on_arc[(h, c), s] for c in Cset) <= quicksum(mvm_ship_on_arc[(f, h), s] for f in Fset),
            name="HubCapacityConstr_{0}_scenario_{1}".format(h, s))

#### Demand Constraint ####
for c in Cset:
    for s in Sset:
        mvm.addConstr(
            mvm_unmet[c, s] + quicksum(mvm_ship_on_arc[(h, c), s] for h in Hset) >= quicksum(demScens[c, s] for s in Sset)/num_scenes,
            name="DemandConstr_{0}_scenario_{1}".format(c, s))

mvm.update()
mvm.optimize()

if mvm.status == GRB.Status.OPTIMAL:
    print "OBJECTIVE VALUE: {0}".format(mvm.objVal)

    if debug:
        print "SOLUTION:"
        for arc in AllArcs:
            if mvm_capinc[arc].x > 0.00001:
                print "Capacity for {0} increased by {1}".format(arc, mvm_capinc[arc].x)

        print("AVERAGE UNMET DEMAND:")
        for c in Cset:
            avgunmet = quicksum(mvm_unmet[c, s].x for s in Sset)/num_scenes
            print("Customer {0}: {1}".format(c, avgunmet))

    print("RUNTIME: {0}".format(mvm.Runtime))
else:
    sys.exit(1)

####### Fix the mean value solution as the first stage solution of stochastic model ############

for arc in AllArcs:
    if mvm_capinc[arc].x > 0.00001:
        capinc[arc].lb = mvm_capinc[arc].x
        capinc[arc].ub = mvm_capinc[arc].x
    else:
        capinc[arc].ub = 0.0

m.update()
m.optimize()

if debug:
    print "EXPECTED COST OF MV SOLUTION: {0}".format(m.objVal)

print "VALUE OF STOCHASTIC SOLUTION: {0}".format(m.objVal - exp_cost_stochastic)
