# -*- coding: utf-8 -*-
"""SwingOption_LSMC.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1PIYSlXiS_4AvBklIQtiXTxq3EoRr_hi6

## Valuation of Energy Swing Options
"""

import IPython as ip
import logging
import numpy as np
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings("ignore")
from past.builtins import xrange
from sys import version 
import seaborn as sns
import pandas as pd
import json
from io import StringIO

class SwingOptionsLSMC2(object):
    """ Class for Energy swing options pricing using Thanawalla, R.T (2005):
    "Ref."
    S0 : float : initial stock/index level
    strike : float : strike price
    T : float : time to maturity (in year fractions)
    M : int : grid or granularity for time (in number of total points)
    gamma : float : constant risk-free short rate
    div :    float : dividend yield
    sigma :  float : volatility factor in diffusion term 
    ACQ : int : Annual Contract Quantity
    DCQ : int : Daily Contract Quantity
    ToP : int : Take-or-Pay quantity
    simulations : int : number of simulated price paths
    deg : int : degree of the polynomial used in the regression
    """

    def __init__(self, S0, strike, T, M, gamma, div, sigma, ACQ, DCQ, ToP, simulations, deg, providedPrice_matrix):
        try:
            self.S0 = float(S0)
            self.strike = float(strike)
            assert T > 0
            self.T = float(T)
            assert M > 0
            self.M = int(M)
            assert gamma >= 0
            self.gamma = float(gamma)
            assert div >= 0
            self.div = float(div)
            assert sigma > 0
            self.sigma = float(sigma)
            assert ACQ > 0
            self.ACQ = int(ACQ)
            assert DCQ > 0
            self.DCQ = int(DCQ)
            assert ToP > 0
            self.ToP = int(ToP)
            assert simulations > 0
            self.simulations = int(simulations)
            assert deg > 0
            self.deg = int(deg)
            self.providedPrice_matrix = providedPrice_matrix
        except ValueError:
            print('Error passing Options parameters')

        if S0 < 0 or strike < 0 or T <= 0 or M <= 0 or gamma < 0 or div < 0 or sigma < 0 or ACQ <=0 or DCQ <= 0 or ToP < 0 or simulations <=0 or deg <= 0:
            raise ValueError('Error: Negative inputs not allowed')

        self.rights = int(self.ACQ/self.DCQ)
        self.time_unit = self.T / float(self.M)
        self.discount = np.exp(-self.gamma * self.time_unit)
        self.actions = [0, self.DCQ]
        self.simulations_changed = False
        
    def is_odd(self, num):
        return num & 1 and True or False

    def MCprice_matrix(self, seed = 123):
        """ Returns MC price matrix rows: time columns: price-path simulation """
        np.random.seed(seed)
        if self.is_odd(self.simulations):
            self.simulations += 1; #[-1,1][random.randrange(2)]
            self.simulations_changed = True;
        MCprice_matrix = np.zeros((self.M + 1, self.simulations), dtype=np.float64)
        MCprice_matrix[0,:] = self.S0
        for t in xrange(1, self.M + 1):
            brownian = np.random.standard_normal(int(self.simulations / 2))
            brownian = np.concatenate((brownian, -brownian))
            MCprice_matrix[t, :] = (MCprice_matrix[t - 1, :]
                                  * np.exp((self.gamma - self.sigma ** 2 / 2.) * self.time_unit
                                  + self.sigma * brownian * np.sqrt(self.time_unit)))
        if self.simulations_changed:
          MCprice_matrix = MCprice_matrix[:,:-1]
          self.simulations -= self.simulations
        return MCprice_matrix


    @property
    def value_vector(self):
        """Backward induction"""
        if self.providedPrice_matrix is None:
          self.MCprices = np.copy(self.MCprice_matrix()[1:,:])
        else:
          self.MCprices = np.copy(self.providedPrice_matrix)
          self.MCprices = self.MCprices[1:,:]
        
        self.MCprices = np.concatenate((np.array([self.MCprices[0,:]]),self.MCprices),axis=0)
        T = self.MCprices.shape[0]-1
        sims = self.MCprices.shape[1]
        self.policy = np.zeros((T+1,self.rights+1,sims))

        self.h = np.zeros((len(self.actions),sims))
        Value = np.zeros((self.rights+1,sims))
        
        for r in range(1,self.rights+1):
          for a in range(len(self.actions)):
            self.h[a,:] = np.maximum(self.actions[a]*(self.MCprices[-1,:]-self.strike), 0)

          Value[r,:] = np.max(self.h, axis=0)  # <-------- Double Check - This is V_{T}

        V_copy = np.copy(Value)

        for t in range(T, 0 , -1):
          V_copy = np.copy(Value)
          Value = np.zeros((self.rights+1,sims))
          self.h = np.zeros((len(self.actions),sims))
          
          for r in range(max(self.rights-t+1,0),self.rights+1):
            if r == 0:
              Value[0,:] = 0
              continue;

            X = self.MCprices[t,:]
            Y = self.discount*V_copy[r-1,:]
            regression = np.polyfit(X, Y, self.deg)
            continuation_value = np.polyval(regression, X)

            for a in range(len(self.actions)):
              self.h[a,:] = np.maximum(self.actions[a]*(self.MCprices[t,:] - self.strike), 0) + continuation_value

            idx = np.argmax(self.h, axis=0)
            val = np.max(self.h, axis=0)
            
            Y = self.discount*V_copy[r,:]
            regression = np.polyfit(X, Y, self.deg)
            continuation_value = np.polyval(regression, X)            
            optimal_action = np.empty(self.simulations)

            for k in range(len(idx)):
              optimal_action[k] = self.actions[int(idx[k])]
            
            Value[r,:] = np.where(val > continuation_value,
                                          np.maximum(optimal_action[:]*(self.MCprices[t,:]-self.strike), 0) + self.discount*V_copy[r-1,:], Y[:])
        
            self.policy[t,r,:] = np.where(val > continuation_value,
                                          -1, 0)

        return Value, self.policy[1:,:,:]


    @property
    def price(self):
      V_hat = np.mean(self.value_vector[-1], axis=1)
      return self.discount*V_hat[-1]

# Optimal Pricing(Valuation)

df = pd.read_csv('rt_hb_north_paths.csv')
P = df.T.to_numpy()
P = P[0:240,0:100]
SwingOption = SwingOptionsLSMC2(1, 20, 1, 24, 0.06, 0.06, 0.59, 40, 5, 10, 100, 5, providedPrice_matrix = P)
SwingOption.price