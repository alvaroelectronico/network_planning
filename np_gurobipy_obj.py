import pandas as pd
from hard_coded_data import *
import gurobipy as gp
import os
from gurobipy import GRB
from read_data import read_data
import time

class NP_problem:
    def __init__(self, name, input_folder):
        self.name = name
        self.input_folder = input_folder
        self.lots = list()
        self.sites = list()
        self.nodes = list()
        self.cells = list()
        self.existing_sites = list()
        self.potential_sites = list()
        self.initial_capacity = dict()
        self.max_capacity = dict()
        self.demand = dict()
        self.coverage = list()
        self.existing_node_in_site = list()
        self.potential_node_in_site = list()
        self.existing_cell_in_site_node = list()
        self.potential_cell_in_site_node = list()
        self.site_cells_lighting_lot_node = list()
        self.lots_covered_by_site_node_cell = list()
        self.model = gp.Model("network_dimensioning")
        self.solver_params = dict()
        self.read_data()

    def read_data(self):
        print("Reading data")
        start_time = time.time()

        self.lots, self.sites, self.nodes, self.cells, self.existing_sites, self.potential_sites, self.initial_capacity,\
        self.max_capacity, self.demand, self.coverage, self.existing_node_in_site, self.potential_node_in_site, \
        self.existing_cell_in_site_node, self.potential_cell_in_site_node, self.site_cells_lighting_lot_node,\
        self.lots_covered_by_site_node_cell\
            = read_data(self.input_folder)

        print("Data read. Time: {}".format(time.time() - start_time))

    def build_model(self):
        start_time_g = time.time()
        start_time = time.time()
        self.model = gp.Model("network_dimensioning")
        print("Building model")
        v01NewSite = self.model.addVars(self.potential_sites,
                                   vtype=GRB.BINARY,
                                   obj=(pCAPEX_NEW_SITE + pOPEX_SITE),
                                   name="v01NewSite")
        v01NewNode = self.model.addVars(self.potential_node_in_site,
                                   vtype=GRB.BINARY,
                                   obj=pCAPEX_NEW_NODE + pOPEX_NODE,
                                   name="v01NewNode")
        v01NewCell = self.model.addVars(self.potential_cell_in_site_node,
                                   vtype=GRB.BINARY,
                                   obj=pCAPEX_NEW_CELL,
                                   name="v01NewCell")

        v01UpgradeCell = self.model.addVars(self.existing_cell_in_site_node,
                                       vtype=GRB.BINARY,
                                       obj=pCAPEX_UPGRADE_CEll,
                                       name="v01UpgradeCell")

        vFinalCapacity = self.model.addVars(self.sites, self.nodes, self.cells,
                                       vtype=GRB.CONTINUOUS,
                                       lb=0,
                                       obj=0,
                                       name="vFinalCapacity")

        vTrafficOfCell = self.model.addVars(self.coverage,
                                       vtype=GRB.CONTINUOUS,
                                       lb=0,
                                       obj=0,
                                       name="vTrafficOfCell")

        print("Variables defined: {}".format(time.time() - start_time))

        start_time = time.time()
        self.model.ModelSense = GRB.MINIMIZE

        self.model.addConstrs((vFinalCapacity[i] >= self.initial_capacity[i] \
                          for i in self.existing_cell_in_site_node),
                         "MinCellCapacity")
        print("MinCellCapacity constraint built: {}".format(time.time() - start_time))
        start_time = time.time()

        self.model.addConstrs((vFinalCapacity[i] <= self.initial_capacity[i] * v01UpgradeCell[i] + \
                          self.max_capacity[i] * (1 - v01UpgradeCell[i]) \
                          for i in self.existing_cell_in_site_node),
                         "MaxCellCapacityExistingCells")
        print("MaxCellCapacityExistingCells constraint built: {}".format(time.time() - start_time))
        start_time = time.time()

        self.model.addConstrs((vFinalCapacity[i] <= self.max_capacity[i] * v01NewCell[i] \
                          for i in self.potential_cell_in_site_node),
                         "MaxCellCapacityNewCells")
        print("MaxCellCapacityNewCells constraint built: {}".format(time.time() - start_time))
        start_time = time.time()

        self.model.addConstrs((v01NewCell[s, n, c] <= v01NewNode[s, n] \
                          for (s, n, c) in self.potential_cell_in_site_node if (s, n) in self.potential_node_in_site),
                         "NewCellIfNodeExists")
        print("NewCellIfNodeExists constraint built: {}".format(time.time() - start_time))
        start_time = time.time()

        self.model.addConstrs((v01NewNode[s, n] <= v01NewSite[s] \
                          for (s, n) in self.potential_node_in_site if s in self.potential_sites),
                         "NewNodeIfSiteExists")
        print("NewNodeIfSiteExists constraint built: {}".format(time.time() - start_time))
        start_time = time.time()

        self.model.addConstrs((gp.quicksum(vFinalCapacity[s, n, c] for s in self.sites for n in self.nodes for c in self.cells)
                          >=
                          gp.quicksum(self.demand[l, n] for l in self.lots) \
                          for n in self.nodes),
                         "EnoughGlobalCapacity")
        print("EnoughGlobalCapacity constraint built: {}".format(time.time() - start_time))
        start_time = time.time()

        self.model.addConstrs((gp.quicksum(vFinalCapacity[s, n, c] for (s, c) in self.site_cells_lighting_lot_node[l, n])
                          >=
                          self.demand[l, n] for l in self.lots for n in self.nodes),
                         "EnoughCapacityPerLot")
        print("EnoughCapacityPerLot constraint built: {}".format(time.time() - start_time))
        start_time = time.time()

        self.model.addConstrs(
            (gp.quicksum(vTrafficOfCell[s, n, c, l] for l in self.lots_covered_by_site_node_cell[s, n, c])
             <= vFinalCapacity[s, n, c]
             for s in self.sites for n in self.nodes for c in self.cells),
            "MaxTrafficOfCell")

        print("MaxTrafficOfCell constraint built: {}".format(time.time() - start_time))
        start_time = time.time()

        self.model.addConstrs((gp.quicksum(vTrafficOfCell[i[0], n, i[1], l] for \
                                           i in self.site_cells_lighting_lot_node[l, n]) >= self.demand[l, n] for l
                               in self.lots for n
                               in
                               self.nodes),
                              "DemandFullfilment")

        print("DemandFullfilment constraint built: {}".format(time.time() - start_time))
        start_time = time.time()

        print("Model built. Time: {}".format(time.time() - start_time_g))
        # self.model.write("network_planning.lp")

    def set_solver_params(self):
        for param in self.solver_params.keys():
            self.model.setParam(param, self.solver_params[param])

    def solve_model(self):
        self.set_solver_params()
        self.model.optimize()

    def get_df_output_data(self):
        self.output_data = dict(
            case=self.name,
            obj_func=self.model.ObjVal,
            gap=self.model.MIPGap,
            run_time=self.model.Runtime
        )

DATA_PATH = "..\..\..\datos_entrada\csv\casos_prueba"
cases = [c for c in os.listdir(DATA_PATH)]
cases_paths = {c: os.path.join(DATA_PATH, c) for c in os.listdir(DATA_PATH) if os.path.isdir(os.path.join(DATA_PATH, c))}

# case_path = "1000km2_0"
# folder_path = os.path.join(DATA_PATH, case_path)

df_results = pd.DataFrame(columns=["case", "obj_func", "gap", "run_time"])


for case in cases_paths.keys():
    instance = NP_problem(case, cases_paths[case])
    instance.build_model()
    instance.solver_params = dict(TIME_LIMIT=6000, MIPGap=0.01)
    instance.solve_model()
    instance.get_df_output_data()
    df_results = df_results.append(instance.output_data, ignore_index=True)


# print("Total cost: {}".format(instance.model.ObjVal))

# print()
# print("New sites")
# for site in [s for s in potential_sites if v01NewSite[s].X == 1]:
#     print("{}".format(site))
#
# print()
# print("New nodes")
# for (site, node) in [i for i in potential_node_in_site if v01NewNode[i].X == 1]:
#     print("{}-  {}".format(site, node))
#
# print()
# print("New cells")
# for (site, node, cell) in [i for i in potential_cell_in_site_node if v01NewCell[i].X == 1]:
#     print("{}-{}-{}".format(site, node, cell))
#
# print()
# print("Upgrade cells")
# for (site, node, cell) in [i for i in existing_cell_in_site_node if v01UpgradeCell[i].X == 1]:
#     print("{}-{}-{}".format(site, node, cell))
#
# print("Total cost: {}".format(model.ObjVal))
#
# print()
# print("Final capacity")
# for (site, node, cell) in [(s, n, c) for s in sites for n in nodes for c in cells if vFinalCapacity[s, n, c].X > 0]:
#     print("{} - {} - {}: {}".format(site, node, cell, vFinalCapacity[site, node, cell].X))
#
# print("Traffic")
# for i in [j for j in coverage if vTrafficOfCell[j].X > 0]:
#     print("{} - {} - {} - {}: {}".format(i[0], i[1], i[2], i[3], vTrafficOfCell[i].X))
