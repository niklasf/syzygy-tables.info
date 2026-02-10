import chess
import collections
import random
import queue
from typing import Optional

# Based on https://github.com/JamesBrill/Markov-Chain-Text-Generator/blob/master/textgen.py

class MarkovChain:
    def __init__(self, tokens: list[str], order: int) -> None:
        assert order <= len(tokens)
        self.markov_chain: collections.defaultdict[str, collections.defaultdict[str, int]] = collections.defaultdict(lambda: collections.defaultdict(int))
        current_state_queue: queue.Queue[str] = queue.Queue()
        current_state = ""
        for index, token in enumerate(tokens):
            if index < order:
                current_state_queue.put(token)
                if index == order - 1:
                    current_state = ' '.join(list(current_state_queue.queue))
            elif index < len(tokens):
                current_state_queue.get()
                current_state_queue.put(token)
                next_state = ' '.join(list(current_state_queue.queue))
                self.markov_chain[current_state][next_state] += 1
                current_state = next_state

    def get_random_state(self, rng: random.Random) -> str:
        uppercase_states = [state for state in self.markov_chain.keys() if state[0].isupper()]
        if len(uppercase_states) == 0:
            return rng.choice(list(self.markov_chain.keys()))
        return rng.choice(uppercase_states)

    def get_next_state(self, state: str, rng: random.Random) -> Optional[str]:
        next_state_items = list(self.markov_chain[state].items())
        next_states = [x[0] for x in next_state_items]
        next_state_counts = [x[1] for x in next_state_items]
        total_count = sum(next_state_counts)
        next_state_probabilities = []
        probability_total: float = 0
        for next_state_count in next_state_counts:
            probability = float(next_state_count) / total_count
            probability_total += probability
            next_state_probabilities.append(probability_total)
        sample = rng.random()
        for index, next_state_probability in enumerate(next_state_probabilities):
            if sample <= next_state_probability:
                return next_states[index]
        return None

    def generate_link(self, rng: random.Random) -> Optional[str]:
        # Generate cheap position
        board = chess.Board.empty()
        for _ in range(rng.randint(0, 5)):
            board.set_piece_at(rng.choice(chess.SQUARES), chess.Piece(rng.choice(chess.PIECE_TYPES), rng.choice(chess.COLORS)))
        return f"/?fen={board.fen()}"

    def generate_text(self, words: int, rng: random.Random) -> str:
        state = self.get_random_state(rng)
        text = state.split()[:words]
        while len(text) < words:
            state = self.get_next_state(state, rng) or self.get_random_state(rng)
            word = state.split()[-1]
            if rng.randint(0, 100) < 5:
                text.append(f"<a href=\"{self.generate_link(rng)}\">{word}</a>")
            else:
                text.append(word)
        text.append(f"<a href=\"{self.generate_link(rng)}\">...</a><br>")
        return ' '.join(text)


TRAINING_DATA = """
Chess is a board game for two players, played on a square board consisting of 64 squares arranged in an 8×8 grid. The players, referred to as "White" and "Black", each control sixteen pieces: one king, one queen, two rooks, two bishops, two knights, and eight pawns, with each piece type having a different pattern of movement. An enemy piece may be captured (removed from the board) by moving one's own piece onto the square it occupies. The object of the game is to "checkmate" (threaten with inescapable capture) the enemy king. There are also several ways a game can end in a draw.

The recorded history of chess dates back to the emergence of chaturanga in 7th-century India. Chaturanga is also thought to be an ancestor of similar games like janggi, xiangqi, and shogi. After its introduction to Persia, it spread to the Arab world and then to Europe. The modern rules of chess emerged in Europe at the end of the 15th century, becoming standardized and gaining universal acceptance by the end of the 19th century. Today, chess is one of the world's most popular games, with millions of players worldwide.

Organized chess arose in the 19th century. International chess competitions today are governed by the International Chess Federation FIDE (Fédération Internationale des Échecs). The first universally recognized World Chess Champion, Wilhelm Steinitz, claimed his title in 1886; Gukesh Dommaraju is the current World Champion, having won the title in 2024.

A large body of chess theory has developed since the game's inception. Aspects of art are found in chess composition, and chess has in turn influenced Western culture and the arts, and has relevance to other fields such as mathematics, computer science, and psychology. One of the goals of early computer scientists was to create a chess-playing machine. In 1997, Deep Blue became the first computer to win a match with a reigning World Champion when it defeated Garry Kasparov. The chess engines of today are significantly stronger than the best human players and have greatly influenced the development of chess theory. Chess, however, is not a solved game.

White moves first, after which players alternate turns. One piece is moved per turn (except when castling, during which two pieces are moved). In the diagrams, dots mark the squares to which each type of piece can move if unoccupied by friendly pieces and there are no intervening piece(s) of either color (except the knight, which leaps over any intervening pieces). With the sole exception of en passant, a piece captures an enemy piece by moving to the square it occupies, removing it from play and taking its place. The pawn is the only piece that does not capture the way it moves, and it is the only piece that moves and captures in only one direction (forwards from the player's perspective). A piece is said to control empty squares on which it could capture, attack squares with enemy pieces it could capture, and defend squares with pieces of the same color on which it could recapture. Moving is compulsory; a player may not skip a turn, even when having to move is detrimental.

Draw by agreement: In tournament chess, draws are most commonly reached by mutual agreement between the players. The correct procedure is to make a move, to verbally offer the draw, and then to start the opponent's clock. If a draw is offered before making a move, the opponent has the right to ask the player to make a move before making their decision on whether or not to accept the draw offer. Traditionally, players were allowed to agree to a draw at any point in the game, occasionally even without having played a single move. Since the 2000s, efforts have been made to discourage early draws, for example by forbidding draw offers before a certain number of moves have been completed or even forbidding draw offers altogether.

Threefold repetition: This most commonly occurs when neither side is able to avoid repeating moves without incurring a disadvantage. The three occurrences of the position need not occur on consecutive moves for a claim to be valid. The addition of the fivefold repetition rule in 2014 requires the arbiter to intervene immediately and declare the game a draw after five occurrences of the same position, consecutive or otherwise, without requiring a claim by either player. FIDE rules make no mention of perpetual check; this is merely a specific type of draw by threefold repetition.

In competition, chess games are played with a time control. Time controls are generally divided into categories based on the amount of time given to each player, which range from classical time controls, which allot about 2 hours or more to each player and which can take upwards of seven hours (even longer if adjournments are permitted), to bullet chess, in which players receive less than three minutes each. Between these are rapid chess (ten to sixty minutes per player) and blitz chess (three to ten minutes). Non-classical chess is sometimes referred to as fast chess.

Until about 1980, the majority of English language chess publications used descriptive notation, in which files are identified by the initial letter of the piece that occupies the first rank at the beginning of the game. In descriptive notation, the common opening move 1.e4 is rendered as "1.P-K4" ("pawn to king four"). Another system, ICCF numeric notation, is recognized by the International Correspondence Chess Federation.

Chess strategy is concerned with the evaluation of chess positions and with setting up goals and long-term plans for future play. During the evaluation, players must take into account numerous factors such as the value of the pieces on the board, control of the center and centralization, the pawn structure, king safety, and the control of key squares or groups of squares (for example, diagonals, open files, and dark or light squares).

In chess, tactics generally refer to short-term maneuvers—so short-term that they can be calculated in advance by a human player. The possible depth of calculation depends on the player's ability. In quiet positions with many possibilities on both sides, a deep calculation is more difficult and may not be practical, while in positions with a limited number of forced variations, strong players can calculate long sequences of moves.

In chess, the endgame tablebase, or simply the tablebase, is a computerised database containing precalculated evaluations of endgame positions. Tablebases are used to analyse finished games, as well as by chess engines to evaluate positions during play. Tablebases are typically exhaustive, covering every legal arrangement of a specific selection of pieces on the board, with both White and Black to move. For each position, the tablebase records the ultimate result of the game (i.e. a win for White, a win for Black, or a draw) and the number of moves required to achieve that result, both assuming perfect play. Because every legal move in a covered position results in another covered position, the tablebase acts as an oracle that always provides the optimal move.

Tablebases have profoundly advanced the chess community's understanding of endgame theory. Some positions which humans had analysed as draws were proven to be winnable; in some cases, tablebase analysis found a mate in more than five hundred moves, far beyond the ability of humans, and beyond the capability of a computer during play. This caused the fifty-move rule to be called into question, since many positions were discovered that were winning for one side but drawn during play because of this rule. Initially, some exceptions to the fifty-move rule were introduced, but when more extreme cases were later discovered, these exceptions were removed. Tablebases also facilitate the composition of endgame studies.

Computer chess is one of the oldest domains of artificial intelligence, having begun in the early 1930s. Claude Shannon proposed formal criteria for evaluating chess moves in 1949. In 1951, Alan Turing designed a primitive chess-playing program, which assigned values for material and mobility; the program "played" chess based on Turing's manual calculations.[9] However, even as competent chess programs began to develop, they exhibited a glaring weakness in playing the endgame. Programmers added specific heuristics for the endgame – for example, the king should move to the center of the board.[10] However, a more comprehensive solution was needed.

For each position, the tablebase evaluates the situation separately for White-to-move and Black-to-move. Assuming that White has the queen, almost all the positions are White wins, with checkmate forced in no more than ten moves. Some positions are draws because of stalemate or the unavoidable loss of the queen.

"The idea is that a database is made with all possible positions with a given material [note: as in the preceding section]. Then a subdatabase is made of all positions where Black is mated. Then one where White can give mate. Then one where Black cannot stop White giving mate next move. Then one where White can always reach a position where Black cannot stop [them] from giving mate next move. And so on, always a ply further away from mate until all positions that are thus connected to mate have been found. Then all of these positions are linked back to mate by the shortest path through the database. That means that, apart from 'equi-optimal' moves, all the moves in such a path are perfect: White's move always leads to the quickest mate, Black's move always leads to the slowest mate."

Each position is evaluated as a win or loss in a certain number of moves. At the end of the retrograde analysis, positions which are not designated as wins or losses are necessarily draws.

According to the method described above, the tablebase must allow the possibility that a given piece might occupy any of the 64 squares. In some positions, it is possible to restrict the search space without affecting the result. This saves computational resources and enables searches which would otherwise be impossible.

Bleicher has designed a commercial program called "Freezer", which allows users to build new tablebases from existing Nalimov tablebases with a priori information. The program could produce a tablebase for positions with seven or more pieces with blocked pawns, even before tablebases for seven pieces became available.

Syzygy tablebases were developed by Ronald de Man and released in April 2013 in a form optimized for use by a chess program during search. This variety consists of two tables per endgame: a smaller WDL (win/draw/loss) table which contains knowledge of the 50-move rule, and a larger DTZ table (distance to zero ply, i.e., pawn move or capture). The WDL tables were designed to be small enough to fit on a solid-state drive for quick access during search, whereas the DTZ form is for use at the root position to choose the game-theoretically quickest distance to resetting the 50-move rule while retaining a winning position, instead of performing a search. Syzygy tablebases are available for all 6-piece endings, and are now supported by many top engines, including Stockfish, Leela, Dragon, and Torch.

Mark Dvoretsky, an International Master, chess trainer, and author, took a more permissive stance. He was commenting in 2006 on a study by Harold van der Heijden, published in 2001, which reached the position at right after three introductory moves. The drawing move for White is 4. Kb4!! (and not 4. Kb5), based on a mutual zugzwang that may occur three moves later.

Originally, an endgame tablebase was called an "endgame data base" or "endgame database". This name appeared in both EG and the ICCA Journal starting in the 1970s, and is sometimes used today. According to Haworth, the ICCA Journal first used the word "tablebase" in connection with chess endgames in 1995.[79] According to that source, a tablebase contains a complete set of information, but a database might lack some information.

An EGTB is a set of endgames. Each endgame is a set of records about positions’ information. All involved positions in an endgame must have the same material. Typically each position's record is associated with an integer number which informs how far that position is from mating/being mated or converting (depends on the type of its metrics).

Based on values of those integer numbers it can answer directly two questions of the EGTB: 1) for a given position it is a draw or a win/loss position and 2) how far it is from mating/being mated or converting. To answer the 3rd question, the best move of a position can be indirectly calculated: generate all legal moves, make them, probe all new positions, compare probing scores for the highest one and the associated move is the best one.

Theoretically, we can add more information to each position’s record. However, due to the large number of involved positions, any additional information may make the whole EGTB become significantly larger. Thus so far none of the popular EGTBs store any extra information and their records actually contain those integers only.

All records of an endgame are simply organized as two arrays (one array for one side/colour). In other words, each item in those arrays is an integer and its index on an array is mapped to a unique position. For a given chess position, we will calculate its index and then access its data record/integer via that index without searching.

The size of an endgame depends on:

    The number of involving pieces: more pieces, the bigger size
    Type of pieces: for standard chess, more Pawns is the smaller size
    Type of metric
    The largest value: the integer number should be large enough to cover the largest value. Different endgames will have different largest values. Thus some endgames need only one byte per item but some need 2 bytes
    Indexing: The algorithms to map between an array item and a position
    Compress ratio

So far the size of an EGTB is the most important factor of success.

To summarize the different metrics of tablebases, each metric has its strengths and weaknesses. Nalimov's DTM EGTs are widely and commercially available, and used by many chess engines or chess GUIs. DTC EGTs are more easily computed and stored as they involve smaller depth ranges and are more compressible. For endgames with less or equal to 5 pieces on the board, KNNKP comes closest to requiring more than one Byte per position to store DTM: maxDTM = 115 (1-0) and 73 (0-1) necessitating 190 values in the EGT. For KPPKP, maxDTM = 127 (1-0) but only 42 (0-1). But for certain 6-piece endgames, one Byte is not enough: maxDTM = 262 for a KRNKNN position. The DTC and DTZ metrics increasingly postpone the need for two Bytes per position in an uncompressed EGT, but KRBNKQN has maxDTC = maxDTZ = 517 (0-1), both wtm and btm.

In extremis, the unmoderated use of DTM, DTC or DTZ EGTs will let slip a winnable position in the context of the 50-move rule ... hence the marginal need for the DTR and DTZR metrics, coupled with the ability to recompute DTR/DTZR EGTs in the context of a limited move-budget.

Every position is assigned to a unique index to specify the location of the information stored about it. The main purpose of indexing is to locate and read the information (from databases) such as distance to mate for a given position based on its index.

There are two main aims when generating the index number. The easier the algorithm to generate the index from any given position, the faster will be the probing of the tablebase as well as the generation of it. But the second aim is to get a relatively small range of index numbers, to keep the size of the file as small as possible.

The most straightforward way would be to for every piece on the board use 6 bit (1-64 squares).
"""


MARKOV_CHAIN = MarkovChain(TRAINING_DATA.replace("\n", "<br> ").split(), 1)
