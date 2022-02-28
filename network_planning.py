import pandas as pd
import os
from pyomo.environ import *
from dask import dataframe as dd

# DATA_PATH =  "D:\Dropbox\\academico\produccion\\articulos\en_curso\\network_planning\datos_entrada\csv\casos_daniele"
from torch.cuda import init


from werkzeug.debug import Console

DATA_PATH = "..\..\datos_entrada\csv\\analisis_rendimiento\\010"
case_path = "010_12scope_2020_13_1805"
# DATA_PATH = "..\..\datos_entrada\csv\casos_daniele"
# case_path = "5000km2_0"
pCAPEX_UPGRADE_CEll = 5868
pCAPEX_NEW_CELL = 11737
pCAPEX_NEW_SITE = 28855
pCAPEX_NEW_NODE = 36770
pOPEX_SITE = 1960
pOPEX_NODE = 0


def read_data(folder_path):network
    df_initial_capacity = pd.read_csv(os.path.join(folder_path, "capacityi.csv"))
    df_potential_capacity = pd.read_csv(os.path.join(folder_path, "capacityp.csv"))
    df_existing_sites = pd.read_csv(os.path.join(folder_path, "existing_sites.csv"))
    df_potential_sites = pd.read_csv(os.path.join(folder_path, "potential_sites.csv"))
    df_demand = pd.read_csv(os.path.join(folder_path, "traffic_demand.csv"))
    df_coverage = pd.read_csv(os.path.join(folder_path, "coverage.csv"))

    df_initial_capacity.set_index(['site_id', 'node', 'cell'], inplace=True)
    initial_capacity = df_initial_capacity.to_dict(orient="dict")['capacity']
    df_potential_capacity.set_index(['site_id', 'node', 'cell'], inplace=True)
    potential_capacity = df_potential_capacity.to_dict(orient="dict")['capacity']

    lots = df_demand.lot_id.unique()
    nodes = df_demand.node.unique()
    cells = df_coverage.cell.unique()
    df_demand.set_index(['lot_id', 'node'], inplace=True)
    demand = df_demand.to_dict(orient='dict')['demand']

    existing_sites = list(df_existing_sites.site_id.unique())
    potential_sites = list(df_potential_sites.site_id.unique())
    sites = existing_sites + potential_sites

    df_coverage.columns
    df_coverage.set_index(['site_id', 'node', 'cell', 'lot_id'], inplace=True)
    coverage = list(df_coverage.index)

    return lots, sites, nodes, cells, existing_sites, potential_sites, initial_capacity, potential_capacity, demand, coverage



# case_path = "001_5"
folder_path = os.path.join(DATA_PATH, case_path)
lots, sites, nodes, cells, existing_sites, potential_sites, initial_capacity, potential_capacity, demand, coverage = read_data(
    folder_path)

existing_node_in_site = list(set([(i[0], i[1]) for i in initial_capacity.keys() if initial_capacity[i] > 0]))

potential_node_in_site = [(s, n) for s in sites for n in nodes
                          if not (s, n) in existing_node_in_site]

existing_cell_in_site_node = [(i[0], i[1], i[2])
                              for i in initial_capacity.keys() if initial_capacity[i] > 0]

potential_cell_in_site_note = [(s, n, c) for s in sites for n in nodes for c in cells
                               if not (s, n, c) in existing_cell_in_site_node]

# Definint the abstract model
model = AbstractModel()

# Sets definition
model.sSites = Set()
model.sExistingSites = Set()
model.sPotentialSites = Set()
model.sNodes = Set()
model.sLots = Set()
model.sCells = Set()

# Compound sets
model.sCoverage = Set(dimen=4)
model.sLotsNodes = Set(dimen=2)
model.sExistingNodesInSites = Set(dimen=2)
model.sPotentialNodesInSites = Set(dimen=2)
model.sPotentialCellsInSitesNodes = Set(dimen=3)
model.sExistingCellsInSitesNodes = Set(dimen=3)

# Parameters
model.pTrafficDemand = Param(model.sLots, model.sNodes, mutable=True)
model.pInitialCapacity = Param(model.sSites, model.sNodes, model.sCells, mutable=True)
model.pMaxCapacity = Param(model.sSites, model.sNodes, model.sCells, mutable=True)
model.pCapexUpgradeCell = Param(mutable=True)
model.pCapexNewCell = Param(mutable=True)
model.pCapexNewNode = Param(mutable=True)
model.pCapexNewSite = Param(mutable=True)
model.pOpexSite = Param(mutable=True)
model.pOpexNode = Param(mutable=True)

# Location variables
model.v01NewSite = Var(model.sPotentialSites, domain=Binary)
model.v01NewNode = Var(model.sPotentialNodesInSites, domain=Binary)
model.v01NewCell = Var(model.sPotentialCellsInSitesNodes, domain=Binary)
model.v01UpgradeCell = Var(model.sExistingCellsInSitesNodes, domain=Binary)
model.vFinalCapacity = Var(model.sSites, model.sNodes, model.sCells, domain=NonNegativeReals)

# Assignment variables
model.vTrafficOfCell = Var(model.sSites, model.sNodes, model.sCells, model.sLots, domain=NonNegativeReals)
model.vTotalCost = Var(domain=NonNegativeReals)


# Constraint rules
def fcDemandFulfilment(model, lot, node):
    # return model.vTotalCost >= 0
    return sum(model.vTrafficOfCell[site, node, cell, lot]
               for site in model.sSites for cell in model.sCells
               if (site, node, cell, lot) in model.sCoverage) >= model.pTrafficDemand[lot, node]


def fcMinCellCapacity(model, site, node, cell):
    return model.vFinalCapacity[site, node, cell] >= model.pInitialCapacity[site, node, cell]


def fcMaxCellCapacity(model, site, node, cell):
    if (site, node, cell) in model.sExistingCellsInSitesNodes:
        return model.vFinalCapacity[site, node, cell] <= \
               model.pInitialCapacity[site, node, cell] * (1 - model.v01UpgradeCell[site, node, cell]) \
               + model.pMaxCapacity[site, node, cell] * model.v01UpgradeCell[site, node, cell]
    else:
        return model.vFinalCapacity[site, node, cell] <= \
               model.pMaxCapacity[site, node, cell] * model.v01NewCell[site, node, cell]


def fcNewCellIfNodeExists(model, site, node, cell):
    if (site, node) in model.sExistingNodesInSites:
        return Constraint.Skip
    else:
        return model.v01NewCell[site, node, cell] <= model.v01NewNode[site, node]


def fcNewNodeIfSiteExists(model, site, node):
    if site in model.sExistingSites:
        return Constraint.Skip
    else:
        return model.v01NewNode[site, node] <= model.v01NewSite[site]


def fcMaxCellTraffic(model, site, node, cell):
    return sum(model.vTrafficOfCell[site, node, cell, lot] for lot in model.sLots if
               (site, node, cell, lot) in model.sCoverage) <= model.vFinalCapacity[site, node, cell]

def fcEnoughCapacityGlobal(model, node):
    return sum(model.vFinalCapacity[site, node, cell] for site in model.sSites for node in model.sNodes
               for cell in model.sCells) >= sum(model.pTrafficDemand[lot, node] for lot in model.sLots)

def fcEnoughCapacityPerLot(model, node, lot):
    return sum(model.vFinalCapacity[site, node, cell] for site in model.sSites for node in model.sNodes
               for cell in model.sCells if (site, node, cell, lot) in model.sCoverage) \
           >= model.pTrafficDemand[lot, node]

# Total cost
def fvTotalCost(model):
    return model.vTotalCost == \
           pCAPEX_NEW_SITE * sum(model.v01NewSite[site] for site in model.sPotentialSites) \
           + pCAPEX_NEW_NODE * sum(model.v01NewNode[site, node] for (site, node) in model.sPotentialNodesInSites) \
           + pCAPEX_NEW_CELL * sum(
        model.v01NewCell[site, node, cell] for (site, node, cell) in model.sPotentialCellsInSitesNodes) \
           + pCAPEX_UPGRADE_CEll * sum(
        model.v01UpgradeCell[site, node, cell] for (site, node, cell) in model.sExistingCellsInSitesNodes) \
           + pOPEX_SITE * sum(model.v01NewSite[site] for site in model.sPotentialSites) \
           + pOPEX_NODE + sum(model.v01NewNode[site, node] for (site, node) in model.sPotentialNodesInSites)


# Objective function
def obj_expression(model):
    return model.vTotalCost


# Activating constraints
# model.cDemandFulfilment = Constraint(model.sLotsNodes, rule=fcDemandFulfilment)
# model.cMinCellCapacity = Constraint(model.sExistingCellsInSitesNodes, rule=fcMinCellCapacity)
# model.cMaxCellCapacity = Constraint(model.sSites, model.sNodes, model.sCells, rule=fcMaxCellCapacity)
# model.cMaxCellTraffic = Constraint(model.sSites, model.sNodes, model.sCells, rule=fcMaxCellTraffic)
# model.cNewCellIfNodeExists = Constraint(model.sPotentialCellsInSitesNodes, rule=fcNewCellIfNodeExists)
# model.cNewNodeIfSiteExists = Constraint(model.sPotentialNodesInSites, rule=fcNewNodeIfSiteExists)
# model.cvTotalCost = Constraint(rule=fvTotalCost)
# model.cEnoughCapacityGlobal = Constraint(model.sNodes, rule=fcEnoughCapacityGlobal)
# model.cEnoughCapacityPerLot = Constraint(model.sNodes, model.sLots, rule=fcEnoughCapacityPerLot)

# Objective function
model.obj_func = Objective(rule=obj_expression)

# Imput data
input_data = {None: {
    'sLots': {None: lots},
    'sSites': {None: sites},
    'sNodes': {None: nodes},
    'sCells': {None: cells},
    'sCoverage': {None: coverage},
    'sLotsNodes': {None: list(demand.keys())},
    'sExistingSites': {None: existing_sites},
    'sPotentialSites': {None: potential_sites},
    'sPotentialNodesInSites': {None: potential_node_in_site},
    'sExistingNodesInSites': {None: existing_node_in_site},
    'sExistingCellsInSitesNodes': {None: existing_cell_in_site_node},
    'sPotentialCellsInSitesNodes': {None: potential_cell_in_site_note},
    'pTrafficDemand': demand,
    'pInitialCapacity': initial_capacity,
    'pMaxCapacity': potential_capacity
}}

# Creating model instance
instance = model.create_instance(input_data)

# Setting the solver

print("Total cost: {}".format(instance.vTotalCost.value))

print()
print("New sites")
for site in [s for s in instance.sPotentialSites if instance.v01NewSite[s].value == 1]:
    print("{}".format(site))

print()
print("New nodes")
for (site, node) in [(s, n) for (s, n) in instance.sPotentialNodesInSites if instance.v01NewNode[s, n].value == 1]:
    print("{}, {}".format(site, node))

print()
print("New cells")
for (site, node, cell) in [(s, n, c) for (s, n, c) in instance.sPotentialCellsInSitesNodes if instance.v01NewCell[s, n, c].value == 1]:
    print("{}, {}, {}".format(site, node, cell))


print()
print("Upgraded cells")
for (site, node, cell) in [(s, n, c) for (s, n, c) in instance.sExistingCellsInSitesNodes if instance.v01UpgradeCell[s, n, c].value == 1]:
    print("{}, {}, {}".format(site, node, cell))

print("Total cost: {}".format(instance.vTotalCost.value))

# instance.cNewNodeIfSiteExists.pprint()
# instance.cNewCellIfNodeExists.pprint()
# instance.cMaxCellTraffic.pprint()
# instance.cDemandFulfilment.pprint()
# instance.cvTotalCost.pprint()
#
# #
# #
# for (site, node, cell, lot) in [(s, n, c, l) \
#                                 for s in instance.sSites for n in instance.sNodes
#                                 for c in instance.sCells for l in instance.sLots]:
#     if value(instance.vTrafficOfCell[site, node, cell, lot].value or 0) > 0:
#         print("{},{}, {}, {}: {}".format(site, node, cell, lot, instance.vTrafficOfCell[site, node, cell, lot].value))
# #
# #
# #
# print(instance.cDemandFulfilment[('lot_215', '4G')].expr)
# print(instance.cMaxCellTraffic[('existing_site_1', '4G', 'cell_1')].expr)
# #
# #
# print(instance.c[('lot_1', '4G')].expr)
#
#
# s = 'existing_site_1'
# n = '4G'
# c = 'cell_1'
#
# lots_sum = [(s, n, c, lot) for lot in instance.sLots if (s, n, c, lot) in instance.sCoverage]
# lots_sum
#
#
# lots = [lot for lot in instance.sLots if (s, m, c, l) in instance.sCoverage if s == site if n == node if c == cell]
#
# lots = [lot for lot in instance.sLots if ('existing_site_1', '4G', 'cell_1', lot) in instance.sCoverage]
#
#
# lots
#
# type(lots_sum2[0])
#
# ('existing_site_1', '4G', 'cell_1', 'lot_820') in instance.sCoverage