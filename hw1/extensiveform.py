import cPickle
from gurobipy import *

### Read data from file you choose: commont/uncomment to choose the different files
### This file was generated from a separate python file, using the `cPickle' module
### This is just for convenience -- data can be read in many ways in Python

dfile = open('nd1041015.pdat','r')
#dfile = open('nd30-10-20-3000.pdat','r')

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
        obj=arcExpCost[arc],
        vtype=GRB.CONTINUOUS,
        name="CapacityIncrease_({0})".format(arc))

### Second stage vars, amount of extra units to buy to meet demand
unmet = {}
num_scenes = len(Sset)
for c in Cset:
    for s in Sset:
        unmet[c, s] = m.addVar(
            obj=float(unmetCost[c])/num_scenes,
            vtype=GRB.CONTINUOUS,
            name="Unmet_({0}, {0})".format(c, s))

m.modelSense = GRB.MINIMIZE
m.update()

### Transport Capacity Constraints ###
for f in Fset:
    m.addConstr(
        quicksum(curArcCap[f, h] + capinc[f, h] for h in Hset) <= facCap[f],
        name="FacilityToHubCapacityConstr_{0}".format(f))

for h in Hset:
    m.addConstr(
        quicksum(curArcCap[f, h] + capinc[f, h] for f in Fset) >= quicksum(curArcCap[h, c] + capinc[h, c] for c in Cset),
        name="HubToCustomerCapacityConstr_({0})".format(h))

### Demand Constraints ###
for c in Cset:
    for s in Sset:
        m.addConstr(
            quicksum(curArcCap[h, c] + capinc[h, c] for h in Hset) + unmet[c, s] >= demScens[c, s],
            name="DemandConstr_({0}, {0})".format(c, s))

m.update()
m.optimize()

exp_cost_stochastic = m.objVal
print "EXPECTED COST : {0}".format(exp_cost_stochastic)
print "SOLUTION:"
for arc in AllArcs:
    if capinc[arc].x > 0.00001:
        print "Capacity for {0} increased by {1}".format(arc, capinc[arc].x)

for s in Sset:
    for c in Cset:
        if unmet[c, s].x > 0.00001:
            print "Units to buy customer {0} in scenario {1}: {2}".format(c, s, unmet[c, s].x)
print("RUNTIME: {0}".format(m.Runtime))

###############################
##### Mean Value Problem ######
###############################

mvm = Model("Average White Russian Comapny")
### First stage vars, capacity increase decisions
mvm_capinc = {}
for arc in AllArcs:
    mvm_capinc[arc] = mvm.addVar(
        obj=arcExpCost[arc],
        vtype=GRB.CONTINUOUS,
        name="CapacityIncrease_({0})".format(arc))

### Second stage vars, amount of extra units to buy to meet demand
mvm_unmet = {}
for c in Cset:
    for s in Sset:
        mvm_unmet[c, s] = mvm.addVar(
            obj=float(unmetCost[c]),
            vtype=GRB.CONTINUOUS,
            name="Unmet_({0}, {0})".format(c, s))

mvm.modelSense = GRB.MINIMIZE
mvm.update()

### Transport Capacity Constraints ###
for f in Fset:
    mvm.addConstr(
        quicksum(curArcCap[f, h] + mvm_capinc[f, h] for h in Hset) <= facCap[f],
        name="FacilityToHubCapacityConstr_{0}".format(f))

for h in Hset:
    mvm.addConstr(
        quicksum(curArcCap[f, h] + mvm_capinc[f, h] for f in Fset) >= quicksum(curArcCap[h, c] + mvm_capinc[h, c] for c in Cset),
        name="HubToCustomerCapacityConstr_({0})".format(h))

### Demand Constraints ###
for c in Cset:
    for s in Sset:
        mvm.addConstr(
            quicksum(curArcCap[h, c] + mvm_capinc[h, c] for h in Hset) + mvm_unmet[c, s] >= quicksum(demScens[c, s] for s in Sset)/num_scenes,
            name="DemandConstr_({0}, {0})".format(c, s))

mvm.update()
mvm.optimize()

print "COST OF MEAN VALUE MODEL: {0}".format(mvm.objVal)
print "SOLUTION:"
for arc in AllArcs:
    if mvm_capinc[arc].x > 0.00001:
        print "Capacity for {0} increased by {1}".format(arc, mvm_capinc[arc].x)

for s in Sset:
    for c in Cset:
        if mvm_unmet[c, s].x > 0.00001:
            print "Units to buy customer {0} in scenario {1}: {2}".format(c, s, mvm_unmet[c, s].x)
print("RUNTIME: {0}".format(mvm.Runtime))

####### Fix the mean value solution as the first stage solution of stochastic model ############

for arc in AllArcs:
    if mvm_capinc[arc].x > 0.00001:
        capinc[arc].lb = mvm_capinc[arc].x
        capinc[arc].ub = mvm_capinc[arc].x
    else:
        capinc[arc].ub = 0.0

m.update()
m.optimize()

print "EXPECTED COST OF MV SOLUTION: {0}".format(m.objVal)
print "VALUE OF STOCHASTIC SOLUTION: {0}".format(m.objVal - exp_cost_stochastic)