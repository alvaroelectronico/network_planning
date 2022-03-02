import pandas as pd
import os

def read_data(folder_path):
    df_initial_capacity = pd.read_csv(os.path.join(folder_path, "capacityi.csv"))
    df_potential_capacity = pd.read_csv(os.path.join(folder_path, "capacityp.csv"))
    df_existing_sites = pd.read_csv(os.path.join(folder_path, "existing_sites.csv"))
    df_potential_sites = pd.read_csv(os.path.join(folder_path, "potential_sites.csv"))
    df_demand = pd.read_csv(os.path.join(folder_path, "traffic_demand.csv"))
    df_coverage = pd.read_csv(os.path.join(folder_path, "coverage.csv"))

    print("dtaframes read")

    existing_sites = list(df_existing_sites.site_id.unique())
    potential_sites = list(df_potential_sites.site_id.unique())
    sites = existing_sites + potential_sites
    lots = df_demand.lot_id.unique()
    nodes = df_demand.node.unique()
    cells = df_coverage.cell.unique()

    df_initial_capacity.set_index(['site_id', 'node', 'cell'], inplace=True)
    initial_capacity = df_initial_capacity.to_dict(orient="dict")['capacity']
    df_potential_capacity.set_index(['site_id', 'node', 'cell'], inplace=True)
    max_capacity = df_potential_capacity.to_dict(orient="dict")['capacity']
    df_demand.set_index(['lot_id', 'node'], inplace=True)
    demand = df_demand.to_dict(orient='dict')['demand']

    df_coverage.columns
    df_coverage2 = df_coverage.set_index(['site_id', 'node', 'cell', 'lot_id'])
    coverage = list(set(df_coverage2.index))
    print("coverage read")

    existing_node_in_site = list(set([(i[0], i[1]) for i in initial_capacity.keys() if initial_capacity[i] > 0]))
    #
    potential_node_in_site = [(s, n) for s in sites for n in nodes
                               if not (s, n) in existing_node_in_site]
    #
    existing_cell_in_site_node = [(i[0], i[1], i[2])
                                  for i in initial_capacity.keys() if initial_capacity[i] > 0]

    potential_cell_in_site_node = [i for i in initial_capacity.keys() if not i in existing_cell_in_site_node]

    # p01SiteExists = {s: s in existing_sites for s in sites}
    # p01NodeExists = {(s, n): (s,n) in existing_node_in_site for s in sites for n in nodes}
    # p01CellExists = {(s, n, c): ((s, n, c) in initial_capacity.keys() and initial_capacity[s, n, c] > 0)
    #                  for s in sites for n in nodes for c in cells}

    df_coverage['site_cell'] = list(zip(df_coverage['site_id'], df_coverage['cell']))
    df_coverage3 = df_coverage.groupby(by=['lot_id', 'node'])['site_cell'].apply(lambda x: x.values.tolist())
    site_cells_lighting_lot_node = df_coverage3.to_dict()
    print("coverage read")

    # return lots, sites, nodes, cells, existing_sites, potential_sites, initial_capacity, max_capacity, demand, \
    #        coverage, existing_node_in_site, p01SiteExists, p01NodeExists, p01CellExists, site_cells_lighting_lot_node

    return lots, sites, nodes, cells, existing_sites, potential_sites, initial_capacity, max_capacity, demand, \
           coverage, existing_node_in_site, potential_node_in_site, existing_cell_in_site_node, potential_cell_in_site_node, \
           site_cells_lighting_lot_node
