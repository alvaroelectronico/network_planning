import pandas as pd
from hard_coded_data import *
import gurobipy as gp
import os
from gurobipy import GRB
from read_data import read_data
import time
import pickle

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
        self.errors = dict()
        self.solution = dict()
        self.solution_check = ""

    def read_data(self):
        print("Reading data")
        start_time = time.time()

        self.lots, self.sites, self.nodes, self.cells, self.existing_sites, self.potential_sites, self.initial_capacity,\
        self.max_capacity, self.demand, self.coverage, self.existing_node_in_site, self.potential_node_in_site, \
        self.existing_cell_in_site_node, self.potential_cell_in_site_node, self.site_cells_lighting_lot_node,\
        self.lots_covered_by_site_node_cell\
            = read_data(self.input_folder)

        factor = 10000
        self.initial_capacity = {i: self.initial_capacity[i]*factor for i in self.initial_capacity.keys()}
        self.max_capacity = {i: self.max_capacity[i]*factor for i in self.max_capacity.keys()}
        self.demand = {i: self.demand[i]*factor for i in self.demand.keys()}

        print("Data read. Time: {}".format(time.time() - start_time))

    def build_model(self):
        start_time_g = time.time()
        start_time = time.time()
        self.model = gp.Model("network_dimensioning")
        print("Building model")
        self.v01NewSite = self.model.addVars(self.potential_sites,
                                   vtype=GRB.BINARY,
                                   obj=(pCAPEX_NEW_SITE + pOPEX_SITE),
                                   name="v01NewSite")
        self.v01NewNode = self.model.addVars(self.potential_node_in_site,
                                   vtype=GRB.BINARY,
                                   obj=(pCAPEX_NEW_NODE + pOPEX_NODE),
                                   name="v01NewNode")
        self.v01NewCell = self.model.addVars(self.potential_cell_in_site_node,
                                   vtype=GRB.BINARY,
                                   obj=pCAPEX_NEW_CELL,
                                   name="v01NewCell")

        self.v01UpgradeCell = self.model.addVars(self.existing_cell_in_site_node,
                                       vtype=GRB.BINARY,
                                       obj=pCAPEX_UPGRADE_CEll,
                                       name="v01UpgradeCell")

        self.vFinalCapacity = self.model.addVars(self.sites, self.nodes, self.cells,
                                       vtype=GRB.CONTINUOUS,
                                       lb=0,
                                       obj=0,
                                       name="vFinalCapacity")

        self.vTrafficOfCell = self.model.addVars(self.coverage,
                                       vtype=GRB.CONTINUOUS,
                                       lb=0,
                                       obj=0,
                                       name="vTrafficOfCell")

        print("Variables defined: {}".format(time.time() - start_time))

        start_time = time.time()
        self.model.ModelSense = GRB.MINIMIZE

        # Min cell capacity
        self.model.addConstrs((self.vFinalCapacity[i] >= self.initial_capacity[i] \
                          for i in self.existing_cell_in_site_node),
                         "MinCellCapacity")
        print("MinCellCapacity constraint built: {}".format(time.time() - start_time))
        start_time = time.time()

        # Max cell capacity (when upgrading)
        self.model.addConstrs((self.vFinalCapacity[i] <= self.initial_capacity[i] * (1 - self.v01UpgradeCell[i]) + \
                          self.max_capacity[i] * self.v01UpgradeCell[i] \
                          for i in self.existing_cell_in_site_node),
                         "MaxCellCapacityExistingCells")
        print("MaxCellCapacityExistingCells constraint built: {}".format(time.time() - start_time))
        start_time = time.time()

        # Max cell capacity (new cells)
        self.model.addConstrs((self.vFinalCapacity[i] <= self.max_capacity[i] * self.v01NewCell[i] \
                          for i in self.potential_cell_in_site_node),
                         "MaxCellCapacityNewCells")
        print("MaxCellCapacityNewCells constraint built: {}".format(time.time() - start_time))
        start_time = time.time()

        # New cell if node exists
        self.model.addConstrs((self.v01NewCell[s, n, c] <= self.v01NewNode[s, n] \
                          for (s, n, c) in self.potential_cell_in_site_node if (s, n) in self.potential_node_in_site),
                         "NewCellIfNodeExists")
        print("NewCellIfNodeExists constraint built: {}".format(time.time() - start_time))
        start_time = time.time()

        # New node if site exists
        self.model.addConstrs((self.v01NewNode[s, n] <= self.v01NewSite[s] \
                          for (s, n) in self.potential_node_in_site if s in self.potential_sites),
                         "NewNodeIfSiteExists")
        print("NewNodeIfSiteExists constraint built: {}".format(time.time() - start_time))
        start_time = time.time()

        # Enough global capacity
        self.model.addConstrs((gp.quicksum(self.vFinalCapacity[s, n, c]
                        for s in self.sites for n in self.nodes for c in self.cells)
                        >=
                        gp.quicksum(self.demand[l, n] for l in self.lots) \
                        for n in self.nodes),
                        "EnoughGlobalCapacity")
        print("EnoughGlobalCapacity constraint built: {}".format(time.time() - start_time))
        start_time = time.time()

        # Enough capacity per lot
        self.model.addConstrs((gp.quicksum(self.vFinalCapacity[s, n, c] for (s, c)
                         in self.site_cells_lighting_lot_node[l, n])
                          >=
                          self.demand[l, n] for l in self.lots for n in self.nodes),
                         "EnoughCapacityPerLot")
        print("EnoughCapacityPerLot constraint built: {}".format(time.time() - start_time))
        start_time = time.time()

        # Max traffic of cell (depending on final capacity)
        self.model.addConstrs(
            (gp.quicksum(self.vTrafficOfCell[s, n, c, l] for l in self.lots_covered_by_site_node_cell[s, n, c])
             <= self.vFinalCapacity[s, n, c]
             for s in self.sites for n in self.nodes for c in self.cells),
            "MaxTrafficOfCell")
        print("MaxTrafficOfCell constraint built: {}".format(time.time() - start_time))

        # Demand fullfilment
        start_time = time.time()
        self.model.addConstrs((gp.quicksum(self.vTrafficOfCell[i[0], n, i[1], l] for \
                                           i in self.site_cells_lighting_lot_node[l, n]) == self.demand[l, n]
                               for l in self.lots for n in self.nodes),
                              "DemandFullfilment")
        print("DemandFullfilment constraint built: {}".format(time.time() - start_time))
        start_time = time.time()

        # If installing new cells, all three are updated
        self.model.addConstrs((self.v01NewCell[s, n, c] == self.v01NewCell[s, n, c2]
            for s in self.sites for n in self.nodes for c in self.cells for c2 in self.cells
            if (s, n, c) in self.potential_cell_in_site_node and (s, n, c2) in self.potential_cell_in_site_node),
        "AllOrNoneNewCell")

        # If installing new cells, all three are updated
        self.model.addConstrs((self.v01UpgradeCell[s, n, c] == self.v01UpgradeCell[s, n, c2]
                               for s in self.sites for n in self.nodes for c in self.cells for c2 in self.cells
                               if (s, n, c) in self.existing_cell_in_site_node and (
                               s, n, c2) in self.existing_cell_in_site_node),
                              "AllOrNoneUpgradeCell")


        print("Model built. Time: {}".format(time.time() - start_time_g))
        # self.model.write("network_planning.lp")

    def set_solver_params(self):
        for param in self.solver_params.keys():
            self.model.setParam(param, self.solver_params[param])

    def solve_model(self):
        self.set_solver_params()
        self.model.optimize()

    def get_df_performance_data(self):
        self.performance_data = dict(
            case=self.name,
            obj_func=self.model.ObjVal,
            gap=self.model.MIPGap,
            run_time=self.model.Runtime
        )

    def write_lp_file(self):
        self.model.write("network_planning.lp")

    def gen_solution(self):
        self.solution['new_sites'] = [s for s in self.potential_sites if self.v01NewSite[s].X == 1]
        self.solution['new_nodes'] = [(s, n) for (s, n) in self.potential_node_in_site if self.v01NewNode[s, n].X == 1]
        self.solution['new_cells'] = [(s, n, c) for (s, n, c) in self.potential_cell_in_site_node if self.v01NewCell[s, n, c].X == 1]
        self.solution['upgraded_cells'] = [(s, n, c) for (s, n, c) in self.existing_cell_in_site_node if
                                      self.v01UpgradeCell[s, n, c].X == 1]
        self.solution['traffic_of_cell'] = {i: self.vTrafficOfCell[i].X for i in self.coverage}
        self.solution['final_capacity'] = {(s, n, c): self.vFinalCapacity[s, n , c].X for s in self.sites for n in self.nodes for c in self.cells}

    def output_df(self):
        if len(self.solution.keys()) == 0:
            self.gen_solution()
        # Traffic
        df = pd.Series(self.solution["traffic_of_cell"]).reset_index()
        df.columns = ["site", "node", "cell", "lot", "traffic" ]
        df.to_csv("{}_traffic.csv".format(self.name))
        # New sites
        if len(self.solution["new_sites"]) > 0:
            df = pd.Series(self.solution["new_sites"])
            df.columns = ["site"]
            df.to_csv("{}_new_sites.csv".format(self.name))
        # New nodes
        if len(self.solution["new_nodes"]) > 0:
            df = pd.DataFrame.from_dict(self.solution["new_nodes"], orient="columns")
            df.columns = ["site", "node"]
            df.to_csv("{}_new_nodes.csv".format(self.name))
        # New cells
        if len(self.solution["new_cells"]) > 0:
            df = pd.DataFrame.from_dict(self.solution["new_cells"], orient="columns")
            df.columns = ["site", "node", "cell"]
            df.to_csv("{}_new_cells.csv".format(self.name))
        # Upgraded cells
        if len(self.solution["upgraded_cells"]) > 0:
            df = pd.DataFrame.from_dict(self.solution["upgraded_cells"], orient="columns")
            df.columns = ["site", "node", "cell"]
            df.to_csv("{}_upgraded_cells.csv".format(self.name))
        pd.DataFrame(self.performance_data, index=[0]).to_csv("{}_general.csv".format(self.name))
        return df

    def check_solution(self):
        if len(self.solution.keys()) == 0:
            self.gen_solution()

        # Demand is met
        # demand_unmet = [(l, n) for l in self.lots for n in self.nodes
        #                 if self.demand[l, n] > sum(self.solution['traffic_of_cell'][s, n, c, l]
        #                                           for s in self.sites for c in self.cells
        #                                           if (s, n, c, l) in self.coverage)
        #                ]
        # if len(demand_unmet) > 0:
        #     for (l, n) in demand_unmet:
        #         self.solution_check += "ERROR. Demand not met. Lot {}, node {}\n".format(l, n)
        # else:
        #      self.solution_check += "OK. Demand constraint met"


        # Capacity not violated
        capacity_violated = [(s, n, c) for s in self.sites for n in self.nodes for c in self.cells
                             if self.solution["final_capacity"][s, n, c] < sum(self.solution['traffic_of_cell'][s, n, c, l]
                                                                   for l in self.lots if (s, n, c, l) in self.coverage)]
        if len(capacity_violated) > 0:
            for (s, n, c) in capacity_violated:
                self.solution_check += "ERROR. Capacity violated. Site {}, node {}, cell {}\n".format(s, n, c)
        else:
             self.solution_check += "OK. Capacity not violated"
        print(self.solution_check)

def main():
    DATA_PATH = "..\..\..\datos_entrada\csv\casos_20220401"
    cases = [c for c in os.listdir(DATA_PATH)]
    cases_paths = {c: os.path.join(DATA_PATH, c) for c in os.listdir(DATA_PATH) if os.path.isdir(os.path.join(DATA_PATH, c))}

    # case_path = "1000km2_0"
    # folder_path = os.path.join(DATA_PATH, case_path)

    df_performance = pd.DataFrame(columns=["case", "obj_func", "gap", "run_time"])

    ordered_cases_paths_keys = list(cases_paths.keys())
    ordered_cases_paths_keys.sort()

    for case in ordered_cases_paths_keys[:3]:
        instance = NP_problem(case, cases_paths[case])
        instance.build_model()
        instance.solver_params = dict(TIME_LIMIT=6000, MIPGap=0.00)
        instance.solve_model()
        instance.get_df_performance_data()
        df_performance = df_performance.append(instance.performance_data, ignore_index=True)
        df_performance.to_csv(os.path.join(DATA_PATH, "results_network_planning.csv"))
        instance.gen_solution()
        df = instance.output_df()

        with open(case, 'wb') as handle:
            pickle.dump(instance.solution, handle, protocol=pickle.HIGHEST_PROTOCOL)

    df_performance.to_csv("network_planning.csv")

if __name__ == "__main__":
    main()
    print("run completed")

    print("New cells")
    for (site, node, cell) in [i for i in instance.potential_cell_in_site_node if instance.v01NewCell[i].X == 1]:
        print("{}-{}-{}".format(site, node, cell))

    list = [(i[0], i[1]) in [i for i in instance.potential_cell_in_site_node if instance.v01NewCell[i].X == 1]]

    list = [(s, n) for s in instance.sites for n in instance.nodes if sum(instance.v01NewCell[s, n, c].X for c in instance.cells
                                        if (s, n, c) in instance.potential_cell_in_site_node) == 1]

    list2 = [(s, n) for s in instance.sites for n in instance.nodes if sum(instance.v01UpgradeCell[s, n, c].X for c in instance.cells
                                        if (s, n, c) in instance.existing_cell_in_site_node) == 2]
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

# with open(case, 'rb') as handle:
#     b = pickle.load(handle)