"""parkinson.py - Homo Sapiens/Parkinson's disease configuration

This file is part of cMonkey Python. Please see README and LICENSE for
more information and licensing details.
"""
import sys
import logging
import scoring
import microarray
import datamatrix as dm
import membership as memb
import util
import meme
import motif
import stringdb
import organism
import network as nw
import cmonkey

CMONKEY_VERSION = '4.0'
CHECKPOINT_INTERVAL = 3
CHECKPOINT_FILE = None

NUM_ITERATIONS = 2000
CACHE_DIR = 'parkinson_cache'
NUM_CLUSTERS = 267
ROW_WEIGHT = 6.0
MAX_MOTIF_WIDTH = 12

THESAURUS_FILE = 'parkinson_data/synonymThesaurus.csv.gz'

SEQUENCE_TYPES = ['upstream', 'p3utr']
SEARCH_DISTANCES = {'upstream': (0, 700), 'p3utr': (0, 831)}
SCAN_DISTANCES = {'upstream': (0, 700), 'p3utr': (0, 831)}
PROM_SEQFILE = 'parkinson_data/promoterSeqs_ilmn_Homo_sapiens.csv.gz'
P3UTR_SEQFILE = 'parkinson_data/p3utrSeqs_ilmn_Homo_sapiens.csv.gz'
SEQ_FILENAMES = {'upstream': PROM_SEQFILE, 'p3utr': P3UTR_SEQFILE}


class CMonkeyConfiguration(scoring.ConfigurationBase):
    """Leishmania-specific configuration class"""
    def __init__(self, config_params,
                 checkpoint_file=None):
        """create instance"""
        scoring.ConfigurationBase.__init__(self, config_params,
                                           checkpoint_file)

    @classmethod
    def create(cls, matrix_filename, checkpoint_file=None):
        """creates an initialized instance"""
        params = (scoring.ConfigurationBuilder().
                  with_organism('hsa').
                  with_matrix_filenames([matrix_filename]).
                  with_num_iterations(NUM_ITERATIONS).
                  with_cache_dir(CACHE_DIR).
                  with_num_clusters(NUM_CLUSTERS).
                  with_sequence_types(SEQUENCE_TYPES).
                  with_search_distances(SEARCH_DISTANCES).
                  with_scan_distances(SCAN_DISTANCES).
                  build())
        return cls(params, checkpoint_file)

    def read_matrix(self, filename):
        """returns the matrix"""
        matrix_factory = dm.DataMatrixFactory(
            [dm.nochange_filter, dm.center_scale_filter])
        infile = util.DelimitedFile.read(filename, has_header=True,
                                         quote='\"')
        return matrix_factory.create_from(infile)

    def make_membership(self):
        """returns the seeded membership"""
        num_clusters = self.config_params[memb.KEY_NUM_CLUSTERS]
        return memb.ClusterMembership.create(
            self.matrix().sorted_by_row_name(),
            memb.make_kmeans_row_seeder(num_clusters),
            microarray.seed_column_members,
            self.config_params)

    def make_organism(self):
        """returns a configured organism object"""
        nw_factories = [stringdb.get_network_factory2('parkinson_data/human_links_preprocessed.csv', sep=';')]
        return organism.GenericOrganism('hsa', THESAURUS_FILE, nw_factories,
                                        seq_filenames=SEQ_FILENAMES,
                                        search_distances=SEARCH_DISTANCES,
                                        scan_distances=SCAN_DISTANCES)


    def make_row_scoring(self):
        """returns the row scoring function"""
        row_scoring = microarray.RowScoringFunction(
            self.membership(), self.matrix(),
            lambda iteration: ROW_WEIGHT,
            config_params=self.config_params)

        # motifing
        sequence_filters = []
        #print "THESAURUS: ", self.organism().thesaurus()
        #for gene in self.matrix().row_names():
        #    if not gene in self.organism().thesaurus():
        #        print "NOT FOUND: ", gene
        background_file_prom = meme.global_background_file(
            self.organism(), self.matrix().row_names(), 'upstream',
            use_revcomp=True)
        background_file_p3utr = meme.global_background_file(
            self.organism(), self.matrix().row_names(), 'p3utr',
            use_revcomp=True)
        meme_suite_prom = meme.MemeSuite430(
            max_width=MAX_MOTIF_WIDTH,
            background_file=background_file_prom)
        meme_suite_p3utr = meme.MemeSuite430(
            max_width=MAX_MOTIF_WIDTH,
            background_file=background_file_p3utr)

        motif_scoring = motif.MemeScoringFunction(
            self.organism(),
            self.membership(),
            self.matrix(),
            meme_suite_prom,
            seqtype='upstream',
            sequence_filters=sequence_filters,
            pvalue_filter=motif.MinPValueFilter(-20.0),
            weight_func=lambda iteration: 0.0,
            run_in_iteration=scoring.default_motif_iterations,
            config_params=self.config_params)

        network_scoring = nw.ScoringFunction(self.organism(),
                                             self.membership(),
                                             self.matrix(),
                                             lambda iteration: 0.0,
                                             scoring.default_network_iterations,
                                             config_params=self.config_params)

        weeder_scoring = motif.WeederScoringFunction(
            self.organism(), self.membership(), self.matrix(),
            meme_suite_p3utr, 'p3utr',
            pvalue_filter=motif.MinPValueFilter(-20.0),
            weight_func=lambda iteration: 0.0,
            run_in_iteration=scoring.default_motif_iterations,
            config_params=self.config_params)

        return scoring.ScoringFunctionCombiner(
            self.membership(), [row_scoring, network_scoring, motif_scoring, weeder_scoring])


if __name__ == '__main__':
    print('cMonkey (Python port) (c) 2011, Institute for Systems Biology')
    print('This program is licensed under the General Public License V3.')
    print('See README and LICENSE for details.\n')
    if len(sys.argv) < 2:
        print('Usage: ./parkinson.sh <ratio-file> [checkpoint-file]')
    else:
        if len(sys.argv) > 2:
            CHECKPOINT_FILE = sys.argv[2]
        
        conf = CMonkeyConfiguration.create(
            sys.argv[1], checkpoint_file=CHECKPOINT_FILE)
        cmonkey.run_cmonkey(conf)
