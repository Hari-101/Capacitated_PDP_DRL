# -*- coding: utf-8 -*-
"""Problem_cap_pdp.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/15yhqXaOqiXslLt27SmeG2mWA4pxU1FOi
"""

from torch.utils.data import Dataset
import torch
import os
import pickle

from problems.pdp_cap.state_pdp_cap import StatePDP_cap
from utils.beam_search import beam_search

class PDP_cap(object):

    NAME = 'cap_pdp'  # Capacitated Vehicle Routing Problem

    VEHICLE_CAPACITY = 1.0

    @staticmethod
    def get_costs(dataset, pi):  # pi:[batch_size, graph_size]
        assert (pi[:, 0]==0).all(), "not starting at depot"
        assert (torch.arange(pi.size(1), out=pi.data.new()).view(1, -1).expand_as(pi) == pi.data.sort(1)[0]).all(), "not visiting all nodes"

        visited_time = torch.argsort(pi, 1)  # pickup的index < 对应的delivery的index
        assert (visited_time[:, 1:pi.size(1) // 2 + 1] < visited_time[:, pi.size(1) // 2 + 1:]).all(), "deliverying without pick-up"
        # dataset['depot']: [batch_size, 2], dataset['loc']: [batch_size, graph_size, 2]
        dataset = torch.cat([dataset['depot'].reshape(-1, 1, 2), dataset['loc']], dim = 1)  # [batch, graph_size+1, 2]
        d = dataset.gather(1, pi.unsqueeze(-1).expand_as(dataset))  # [batch, graph_size+1, 2]
        # d[:, :-1] do not include -1
        return (d[:, 1:] - d[:, :-1]).norm(p=2, dim=2).sum(1) + (d[:, 0] - d[:, -1]).norm(p=2, dim=1), None


    @staticmethod
    def make_dataset(*args, **kwargs):
        return PDP_cap_Dataset(*args, **kwargs)

    @staticmethod
    def make_state(*args, **kwargs):
        return StatePDP_cap.initialize(*args, **kwargs)
        
    @staticmethod
    def beam_search(input, beam_size, expand_size=None,
                    compress_mask=False, model=None, max_calc_batch_size=4096):

        assert model is not None, "Provide model"

        fixed = model.precompute_fixed(input)
        
        state = StatePDP_cap.make_state(
            input, visited_dtype=torch.int64 if compress_mask else torch.uint8
#            input, visited_dtype=torch.int64 if compress_mask else torch.bool
        )
        def propose_expansions(beam):
            return model.propose_expansions(
                beam, fixed, expand_size, normalize=True, max_calc_batch_size=max_calc_batch_size
            )

        return beam_search(state, beam_size, propose_expansions)

#We would also need to return the demands for each node
#? Find where make_instance appears and what is the nature of args at input?
#--- possibly when we need to make custom datasets

def make_instance(args):
    depot, loc, demand, *args = args
    # grid_size = 1
    # if len(args) > 0:
    #     depot_types, customer_types, grid_size = args
    return {
        'loc': torch.tensor(loc, dtype=torch.float),        #Alterations with respect to VRP code (Check!)
        'depot': torch.tensor(depot, dtype=torch.float),     #Alterations with respect to VRP code (Check!)
        'demand': torch.tensor(demand, dtype=torch.float)
    }

#How to split data into pickup nodes and delivery nodes, from initialisation itself or only post-processing?

class PDP_cap_Dataset(Dataset):

    def __init__(self, filename=None, size=50, num_samples=1000000, offset=0, distribution=None):
        super(PDP_cap_Dataset, self).__init__()

        self.data_set = []
        if filename is not None:
            assert os.path.splitext(filename)[1] == '.pkl'

            with open(filename, 'rb') as f:
                data = pickle.load(f)
            self.data = [make_instance(args) for args in data[offset:offset+num_samples]]

        else:
            
            

              # # From VRP with RL paper https://arxiv.org/abs/1802.04240
              # CAPACITIES = {
              #     10: 20.,
              #     20: 30.,
              #     50: 40.,
              #     100: 50.
              # }         #For adjusting the average number of orders that can be loaded on the resource at a time

            self.data=[]
            min_weight=1/(1.2*(size/2)) #For 20 orders - 0.0417, 10 orders - 0.08
            max_weight=1/(0.25*(size/2)) #For 20 orders - 0.2, 10 orders - 0.4
            for i in range(num_samples):
                #min-> 1/(1.2 x n_orders)
                #max-> 1/(0.25 x n_orders)
                interim_demand = (torch.FloatTensor(size//2).uniform_(min_weight, max_weight))
                instance = {

                        #'loc' refers to the initial location of the resource
                        'loc': torch.FloatTensor(size, 2).uniform_(0, 1),
                        'depot': torch.FloatTensor(2).uniform_(0, 1),
                        #Vehicle capacity shall be 1 and demands in Uniform (0, 1)
                        #Interaction between number of nodes, size range of each node, resource capacity to load 
                              #ratio etc
                        #---Demand of second-half should be negative of the first half
                        'demand': torch.cat((interim_demand, torch.neg(interim_demand)), -1 )    #Setting avg number of loadable orders at a time
                }
                self.data.append(instance)

        self.size = len(self.data)

    def __len__(self):
        return self.size

    def __getitem__(self, idx):
        return self.data[idx]