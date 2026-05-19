"""
I found out about this algorithm while doing my side hustle. It not the sota one for this but it works so I use it into
my code too :)))
"""


class FuzzyFinder:
    """Provides fuzzy finding capabilities using local sequence alignment algorithms."""

    def __init__(self):
        """Initializes the FuzzyFinder."""
        pass

    def smith_waterman(
        self,
        sequence1: str,
        sequence2: str,
        match: int = 2,
        mismatch: int = -1,
        gap: int = -1,
    ) -> float:
        """Performs local sequence alignment using the Smith-Waterman algorithm.

        This algorithm finds the most similar regions between two sequences,
        useful for fuzzy matching text or data.

        Args:
            sequence1 (str): The first input sequence.
            sequence2 (str): The second input sequence to compare against.
            match (int, optional): Score for a character match. Defaults to 2.
            mismatch (int, optional): Penalty for a character mismatch. Defaults to -1.
            gap (int, optional): Penalty for a gap. Defaults to -1.

        Returns:
            float: The highest local alignment score indicating the degree of similarity.
        """

        # sequence 1 for column, sequence 2 for row

        scoring_array = [
            [0 for _ in range(len(sequence1) + 1)] for _ in range(len(sequence2) + 1)
        ]

        max_score = 0
        # now we travel and create dynamic array to calculate the matching score

        for i in range(1, len(sequence2) + 1):
            for j in range(1, len(sequence1) + 1):
                score = 0

                # diagonal checking
                if (
                    sequence2[i - 1] == sequence1[j - 1]
                ):  # we have to minus the index 1 for checking because our matrix start with 1
                    score = max(scoring_array[i - 1][j - 1] + match, score)
                else:
                    score = max(scoring_array[i - 1][j - 1] + mismatch, score)

                # left checking
                score = max(score, scoring_array[i - 1][j] + gap)

                # right checking
                score = max(score, scoring_array[i][j - 1] + gap)

                scoring_array[i][j] = score

                max_score = max(max_score, score)

        return max_score

    def find_multiple_matches(
        self, query: str, target_list: list[str], top_n: int = 1
    ) -> str:
        """Finds the best matching string from a list based on Smith-Waterman score.

        Args:
            query (str): The target string to search for.
            target_list (list[str]): The list of available strings to search within.
            top_n (int, optional): The number of best matches to return. Defaults to 1.

        Returns:
            list[tuple[str, float]]: A list of tuples containing the best matching strings and their scores, sorted by score in descending order.
        """

        list_of_scores = []
        for i in target_list:
            list_of_scores.append((i, self.smith_waterman(query, i)))

        # sort the list of scores
        list_of_scores.sort(key=lambda x: x[1], reverse=True)

        # return the top n scores
        return list_of_scores[:top_n]
