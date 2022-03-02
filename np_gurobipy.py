from torchvision.transforms.functional import vflip

from network_dimensioning.hard_coded_data import *
import gurobipy as gp
import os
import time
from gurobipy import GRB
from network_dimensioning.read_data import read_data

# To debug this py file (to be commented or deleted):
DATA_PATH = "..\..\datos_entrada\csv\casos_daniele"
case_path = "10km2_0"
folder_path = os.path.join(DATA_PATH, case_path)
print("Reading data")
start_time = time.time()

lots, sites, nodes, cells, existing_sites, potential_sites, initial_capacity, max_capacity, demand, \
           coverage, existing_node_in_site, potential_node_in_site, existing_cell_in_site_node, potential_cell_in_site_node, \
           site_cells_lighting_lot_node = read_data(folder_path)

# lots, sites, nodes, cells, existing_sites, potential_sites, pCellInitialCapacity, pCellMaxCapacity, demand, \
# coverage, existing_node_in_site, p01SiteExists, p01NodeExists, p01CellExists, site_cells_lighting_lot_node \
#     = read_data(folder_path)

print("Data read. Time: {}".format(time.time() - start_time))

model = gp.Model("network_dimensioning")


v01NewSite = model.addVars(potential_sites,
                           vtype=GRB.BINARY,
                           obj=(pCAPEX_NEW_SITE + pOPEX_SITE),
                           name="v01NewSite")
v01NewNode = model.addVars(potential_node_in_site,
                           vtype=GRB.BINARY,
                           obj=pCAPEX_NEW_NODE + pOPEX_NODE,
                           name="v01NewNode")
v01NewCell = model.addVars(potential_cell_in_site_node,
                           vtype=GRB.BINARY,
                           obj=pCAPEX_NEW_CELL,
                           name="v01NewCell")

v01UpgradeCell = model.addVars(existing_cell_in_site_node,
                               vtype=GRB.BINARY,
                               obj=pCAPEX_UPGRADE_CEll,
                               name="v01UpgradeCell")

vFinalCapacity = model.addVars(sites, nodes, cells,
                               vtype=GRB.CONTINUOUS,
                               lb=0,
                               obj=0,
                               name="vFinalCapacity")

vTrafficOfCell = model.addVars(coverage,
                               vtype=GRB.CONTINUOUS,
                               lb=0,
                               obj=0,
                               name="vTrafficOfCell")

model.ModelSense = GRB.MINIMIZE


model.addConstrs((vFinalCapacity[i] >= initial_capacity[i] \
                  for i in existing_cell_in_site_node),
                 "MinCellCapacity")

model.addConstrs((vFinalCapacity[i] <= initial_capacity[i] * v01UpgradeCell[i] + \
                                       max_capacity[i] * (1 - v01UpgradeCell[i]) \
                  for i in existing_cell_in_site_node),
                 "MaxCellCapacityExistingCells")

model.addConstrs((vFinalCapacity[i] <= max_capacity[i] * v01NewCell[i] \
                  for i in potential_cell_in_site_node),
                 "MaxCellCapacityNewCells")

model.addConstrs((v01NewCell[s, n, c] <= v01NewNode[s, n] \
                  for (s, n, c) in potential_cell_in_site_node if (s, n) in potential_node_in_site),
                 "NewCellIfNodeExists")

model.addConstrs((v01NewNode[s, n] <= v01NewSite[s] \
                  for (s, n) in potential_node_in_site if s in potential_sites),
                 "NewNodeIfSiteExists")


model.addConstrs((gp.quicksum(vFinalCapacity[s, n, c] for s in sites for n in nodes for c in cells)
                  >=
                  gp.quicksum(demand[l, n] for l in lots) \
                  for n in nodes),
                 "EnoughGlobalCapacity")

model.addConstrs((gp.quicksum(vFinalCapacity[s, n, c] for (s, c) in site_cells_lighting_lot_node[l, n])
                  >=
                  demand[l, n] for l in lots for n in nodes),
                 "EnoughCapacityPerLot")

model.addConstrs((gp.quicksum(vTrafficOfCell[s, n, c, l] for l in lots if (s, c) in site_cells_lighting_lot_node[l, n])
                  <= vFinalCapacity[s, n, c]
                  for s in sites for n in nodes for c in cells),
                 "MaxTrafficOfCell")

model.addConstrs((gp.quicksum(vTrafficOfCell[s, n, c, l] for s in sites for c in cells if \
                              (s, c) in site_cells_lighting_lot_node[l, n]) >= demand[l, n] for l in lots for n in
                  nodes),
                 "DemandFullfilment")

model.write("network_dimensioning.lp")

model.Params.TIME_LIMIT = 100
model.Params.MIPGap = 0.0
model.optimize()


print("Total cost: {}".format(model.ObjVal))

print()
print("New sites")
for site in [s for s in potential_sites if v01NewSite[s].X == 1]:
    print("{}".format(site))

print()
print("New nodes")
for (site, node) in [i for i in potential_node_in_site if v01NewNode[i].X == 1]:
    print("{}-  {}".format(site, node))

print()
print("New cells")
for (site, node, cell) in [i for i in potential_cell_in_site_node if v01NewCell[i].X == 1]:
    print("{}-{}-{}".format(site, node, cell))

print()
print("Upgrade cells")
for (site, node, cell) in [i for i in existing_cell_in_site_node if v01UpgradeCell[i].X == 1]:
    print("{}-{}-{}".format(site, node, cell))

print("Total cost: {}".format(model.ObjVal))

print()
print("Final capacity")
for (site, node, cell) in [(s, n, c) for s in sites for n in nodes for c in cells if vFinalCapacity[s, n, c].X > 0]:
    print("{} - {} - {}: {}".format(site, node, cell, vFinalCapacity[site, node, cell].X))

print("Traffic")
for i in [j for j in coverage if vTrafficOfCell[j].X > 0]:
    print("{} - {} - {} - {}: {}".format(i[0], i[1], i[2], i[3], vTrafficOfCell[i].X))



# v01NewSite = model.addVars(sites,
#                            vtype=GRB.BINARY,
#                            obj=(pCAPEX_NEW_SITE + pOPEX_SITE),
#                            name="v01NewSite")
# v01NewNode = model.addVars(sites, nodes,
#                            vtype=GRB.BINARY,
#                            obj=pCAPEX_NEW_NODE + pOPEX_NODE,
#                            name="v01NewNode")
# v01NewCell = model.addVars(sites, nodes, cells,
#                            vtype=GRB.BINARY,
#                            obj=pCAPEX_NEW_CELL,
#                            name="v01NewCell")
#
# v01UpgradeCell = model.addVars(sites, nodes, cells,
#                                vtype=GRB.BINARY,
#                                obj=pCAPEX_UPGRADE_CEll,
#                                name="v01UpgradeCell")
#
# vFinalCapacity = model.addVars(sites, nodes, cells,
#                                vtype=GRB.CONTINUOUS,
#                                lb=0,
#                                obj=0,
#                                name="vFinalCapacity")
#
# vTrafficOfCell = model.addVars(coverage,
#                                vtype=GRB.CONTINUOUS,
#                                lb=0,
#                                obj=0,
#                                name="v01NewSite")
#
# model.ModelSense = GRB.MINIMIZE
#
# model.addConstrs((v01NewSite[s] <= 1 - p01SiteExists[s] for s in sites),
#                  "NewSiteIfNotExists")
#
# model.addConstrs((v01NewNode[s, n] <= 1 - p01NodeExists[s, n] for s in sites for n in nodes),
#                  "NewNodeIfNotExists")
#
# model.addConstrs((v01NewCell[s, n, c] <= 1 - p01CellExists[s, n, c] for s in sites for n in nodes for c in cells),
#                  "NewCellIfNotExists")
#
# model.addConstrs((v01UpgradeCell[s, n, c] <= p01CellExists[s, n, c] for s in sites for n in nodes for c in cells),
#                  "UpgradeCellIfExists")
#
# model.addConstrs((vFinalCapacity[s, n, c] >= pCellInitialCapacity[s, n, c] * p01CellExists[s, n, c] \
#                   for s in sites for n in nodes for c in cells), \
#                  "MinCellCapacity")
#
# model.addConstrs((vFinalCapacity[s, n, c] <= pCellInitialCapacity[s, n, c] +
#                   +
#                   (pCellMaxCapacity[s, n, c] - pCellInitialCapacity[s, n, c])
#                   * p01CellExists[s, n, c] * v01UpgradeCell[s, n, c]
#                   +
#                   pCellMaxCapacity[s, n, c]
#                   * (1 - p01CellExists[s, n, c]) * v01NewCell[s, n, c] \
#                   for s in sites for n in nodes for c in cells),
#                  "MaxCellCapacity")
#
# model.addConstrs((v01NewCell[s, n, c] <= p01NodeExists[s, n] + v01NewNode[s, n] \
#                   for s in sites for n in nodes for c in cells),
#                  "NewCellIfNodeExists")
#
# model.addConstrs((v01NewNode[s, n] <= p01SiteExists[s] + v01NewSite[s] for s in sites for n in nodes),
#                  "NewNodeIfSiteExists")
#
#
# model.addConstr((gp.quicksum(vFinalCapacity[s, n, c] for s in sites for n in nodes for c in cells)
#                   >=
#                   gp.quicksum(demand[l, n] for l in lots for n in nodes)),
#                  "EnoughGlobalCapacity")
#
# model.addConstrs((gp.quicksum(vFinalCapacity[s, n, c] for (s, c) in site_cells_lighting_lot_node[l, n])
#                   >=
#                   demand[l, n] for l in lots for n in nodes),
#                  "EnoughCapacityPerLot")
#
# model.addConstrs((gp.quicksum(vTrafficOfCell[s, n, c, l] for l in lots if (s, c) in site_cells_lighting_lot_node[l, n])
#                   <= vFinalCapacity[s, n, c]
#                   for s in sites for n in nodes for c in cells),
#                  "MaxTrafficOfCell")
#
# model.addConstrs((gp.quicksum(vTrafficOfCell[s, n, c, l] for s in sites for c in cells if \
#                               (s, c) in site_cells_lighting_lot_node[l, n]) >= demand[l, n] for l in lots for n in
#                   nodes),
#                  "DemandFullfilment")
#
# model.write("network_dimensioning.lp")
#
# model.Params.TIME_LIMIT = 10
# model.Params.MIPGap = 0.05
# model.optimize()
#
#
# print("Total cost: {}".format(model.ObjVal))
#
# print()
# print("New sites")
# for site in [s for s in sites if v01NewSite[s].X == 1]:
#     print("{}".format(site))
#
# print()
# print("New nodes")
# for (site, node) in [(s, n) for s in sites for n in nodes if v01NewNode[s, n].X == 1]:
#     print("{}-  {}".format(site, node))
#
# print()
# print("New cells")
# for (site, node, cell) in [(s, n, c) for s in sites for n in nodes for c in cells if v01NewCell[s, n, c].X == 1]:
#     print("{}-{}-{}".format(site, node, cell))
#
# print()
# print("Upgrade cells")
# for (site, node, cell) in [(s, n, c) for s in sites for n in nodes for c in cells if v01UpgradeCell[s, n, c].X == 1]:
#     print("{}-{}-{}".format(site, node, cell))
#
# print("Total cost: {}".format(model.ObjVal))
#
# # print()
# # print("Final capacity")
# # for (site, node, cell) in [(s, n, c) for s in sites for n in nodes for c in cells if vFinalCapacity[s, n, c].X > 0]:
# #     print("{} - {} - {}: {}".format(site, node, cell, vFinalCapacity[site, node, cell].X))
#
# # print("Traffic")
# # for i in [j for j in coverage if vTrafficOfCell[j].X > 0]:
# #     print("{} - {} - {} - {}: {}".format(i[0], i[1], i[2], i[3], vTrafficOfCell[i].X))
