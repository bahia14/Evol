from random import choices, randint
from copy import deepcopy
from itertools import cycle, islice

from evol import Individual
from evol.helpers.utils import select_arguments


class Population:

    def __init__(self, chromosomes, eval_function, maximize=True):
        self.eval_function = eval_function
        self.generation = 0
        self.individuals = [Individual(chromosome=chromosome) for chromosome in chromosomes]
        self.intended_size = len(chromosomes)
        self.maximize = maximize
        # TODO: add best ever score and the best ever individual

    def __iter__(self):
        return self.individuals.__iter__()

    def __getitem__(self, i):
        return self.individuals[i]

    def __len__(self):
        return len(self.individuals)

    def __repr__(self):
        return f"<Population object with size {len(self)}>"

    @property
    def min_individual(self):
        self.evaluate(lazy=True)
        return min(self, key=lambda x: x.fitness)

    @property
    def max_individual(self):
        self.evaluate(lazy=True)
        return max(self, key=lambda x: x.fitness)

    @classmethod
    def generate(cls, init_func, eval_func, size=100) -> 'Population':
        chromosomes = [init_func() for _ in range(size)]
        return cls(chromosomes=chromosomes, eval_function=eval_func)

    def evolve(self, evolution: 'Evolution', n: int = 1) -> 'Population':
        """Evolve the population."""
        result = deepcopy(self)
        for evo_batch in range(n):
            for step in evolution:
                step.apply(result)
        return result

    def evaluate(self, lazy: bool=False) -> 'Population':
        """Evaluate the individuals in the population
        
        :param lazy: If True, do not evaluate already evaluated individuals. Defaults to False.
        :type lazy: bool
        :return: Population
        """
        for individual in self.individuals:
            individual.evaluate(eval_function=self.eval_function, lazy=lazy)
        return self

    def apply(self, func, **kwargs) -> 'Population':
        """apply(f(Population, **kwargs) -> Population, **kwargs)"""
        return func(self, **kwargs)

    def map(self, func, **kwargs) -> 'Population':
        """map(f(Individual, **kwargs) -> Individual, **kwargs)"""
        self.individuals = [func(individual, **kwargs) for individual in self.individuals]
        return self

    def filter(self, func, **kwargs) -> 'Population':
        """filter(f(Individual, **kwargs) -> bool, **kwargs)"""
        self.individuals = [individual for individual in self.individuals if func(individual, **kwargs)]
        return self

    def update(self, func, **kwargs) -> 'Population':
        """update(f(**kwargs), **kwargs)"""
        func(self, **kwargs)
        return self

    def survive(self, fraction=None, n=None, luck=False) -> 'Population':
        """survive(fraction=None, n=None, luck=False)"""
        if fraction is None:
            if n is None:
                raise ValueError('everyone survives! must provide either "fraction" and/or "n".')
            resulting_size = n
        elif n is None:
            resulting_size = round(fraction*len(self.individuals))
        else:
            resulting_size = min(round(fraction*len(self.individuals)), n)
        self.evaluate(lazy=True)
        if resulting_size == 0:
            raise RuntimeError('no one survived!')
        if resulting_size > len(self.individuals):
            raise ValueError('everyone survives! must provide "fraction" and/or "n" < population size')
        if luck:
            self.individuals = choices(self.individuals, k=resulting_size,
                                       weights=[individual.fitness for individual in self.individuals])
        else:
            sorted_individuals = sorted(self.individuals, key=lambda x: x.fitness, reverse=self.maximize)
            self.individuals = sorted_individuals[:resulting_size]
        return self

    def breed(self, parent_picker, combiner, population_size=None, **kwargs) -> 'Population':
        """breed(parent_picker=f(Population) -> seq[individuals],
                                             f(*seq[chromosome]) -> chromosome,
                                                                    population_size = None, **kwargs)
        """
        parent_picker = select_arguments(parent_picker)
        combiner = select_arguments(combiner)
        if population_size:
            self.intended_size = population_size
        # we ensure that we only select the same group before breeding starts
        size_before_breed = len(self.individuals)
        for _ in range(len(self.individuals), self.intended_size):
            parents = parent_picker(self.individuals[:size_before_breed], **kwargs)
            if not hasattr(parents, '__len__'):
                parents = [parents]
            chromosomes = [individual.chromosome for individual in parents]
            self.individuals.append(Individual(chromosome=combiner(*chromosomes, **kwargs)))
            # TODO: increase generation and individual's ages
        return self

    def mutate(self, func, **kwargs) -> 'Population':
        """mutate(f(chromosome) -> chromosome, ** kwargs)"""
        for individual in self.individuals:
            individual.mutate(func, **kwargs)
        return self


class ContestPopulation(Population):
    def __init__(self, chromosomes, eval_function, matches_per_round=10, individuals_per_match=2, maximize=True):
        Population.__init__(self, chromosomes=chromosomes, eval_function=eval_function, maximize=maximize)
        self.matches_per_round = matches_per_round
        self.individuals_per_match = individuals_per_match

    def evaluate(self, lazy: bool=False) -> 'ContestPopulation':
        if lazy and all(individual.fitness is not None for individual in self):
            return self
        for individual in self.individuals:
            individual.fitness = 0
        for _ in range(self.matches_per_round):
            offsets = [0] + [randint(0, len(self.individuals) - 1) for _ in range(self.individuals_per_match - 1)]
            generators = [islice(cycle(self.individuals), offset, None) for offset in offsets]
            for competitors in islice(zip(*generators), len(self.individuals)):
                scores = self.eval_function(*competitors)
                for competitor, score in zip(competitors, scores):
                    competitor.fitness += score
        return self

    def map(self, func, **kwargs) -> 'Population':
        """map(f(Individual, **kwargs) -> Individual, **kwargs)"""
        Population.map(self, func=func, **kwargs)
        self.reset_fitness()
        return self

    def filter(self, func, **kwargs) -> 'Population':
        """filter(f(Individual, **kwargs) -> bool, **kwargs)"""
        Population.filter(self, func=func, **kwargs)
        self.reset_fitness()
        return self

    def survive(self, fraction=None, n=None, luck=False) -> 'ContestPopulation':
        Population.survive(self, fraction=fraction, n=n, luck=luck)
        self.reset_fitness()
        return self  # If we return the result of Population.survive PyCharm complains that it is of type 'Population'

    def reset_fitness(self):
        for individual in self:
            individual.fitness = None
