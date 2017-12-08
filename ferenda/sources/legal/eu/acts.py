from . import EURLex

class EURLexActs(EURLex):
    alias = "eurlexacts"
    # DTS_SUBDOM can be either ALL_ALL, MNE (National transposition
    # measures), EU_LAW_ALL (legislation + consolidations),
    # LEGISLATION, or CONSLEG (consolidated acts. Maybe EU_LAW_ALL for
    # now is good (excluding national transposition measures cuts ~60%
    # of crap) Unfortunately, we also need teh (DTT = R OR DTT = L)
    # clause (only select requlations or directives) or we'll get a
    # bunch of differnent crap (in sector 6, ie ECJ, and other)
    query_template = "SELECT CELLAR_ID, TI_DISPLAY, DN, DD WHERE DTS_SUBDOM = EU_LAW_ALL AND (DTT = R OR DTT = L) AND DD >= 01/01/2017 <= 31/12/2017 ORDER BY DD ASC"
    
