package org.mdp.hadoop.cli;

import java.io.IOException;

import org.apache.giraph.graph.BasicComputation;
import org.apache.giraph.graph.Vertex;
import org.apache.hadoop.io.DoubleWritable;
import org.apache.hadoop.io.IntWritable;
import org.apache.hadoop.io.NullWritable;
import org.apache.hadoop.io.Text;

/**
 * A PageRank implementation for Giraph that supports nodes
 * with no outlinks.
 *
 * Text: vertex ID type
 * DoubleWritable: vertex value
 * NullWritable: edge value
 * DoubleWritable: message type
 */
public class PageRank extends BasicComputation<Text, DoubleWritable, NullWritable, DoubleWritable> {
	public static final int ITERS = 10;
	public static final double D = 0.85;
	public static final String RJ_AGG_NAME = "random_jump";
	public static final String NUM_V_NAME = "num_vertices";
	public static final IntWritable ONE = new IntWritable(1);

	@Override
	public void compute(Vertex<Text, DoubleWritable, NullWritable> vertex,
			Iterable<DoubleWritable> messages) throws IOException {
		if (getSuperstep() == 0) {
			sendMessageToAllEdges(vertex, new DoubleWritable(0));
		} else if (getSuperstep() == 1) {
			aggregate(NUM_V_NAME, ONE);
		} else {
			int num_vertices = ((IntWritable) getAggregatedValue(NUM_V_NAME)).get();
			double currentRank = 0;

			if (getSuperstep() == 2) {
				currentRank = (double) 1 / num_vertices;
			} else if (getSuperstep() >= 3) {
				for (DoubleWritable message : messages) {
					currentRank += message.get();
				}
				currentRank += ((DoubleWritable) getAggregatedValue(RJ_AGG_NAME)).get() / num_vertices;
				DoubleWritable dw = new DoubleWritable(currentRank);
				vertex.setValue(dw);
			}

			if (getSuperstep() == ITERS + 2) {
				vertex.voteToHalt();
			} else if (getSuperstep() >= 2) {
				long edges = vertex.getNumEdges();
				if (edges > 0) {
					sendMessageToAllEdges(vertex, new DoubleWritable(D * currentRank / edges));
					aggregate(RJ_AGG_NAME, new DoubleWritable((1 - D) * currentRank));
				} else {
					aggregate(RJ_AGG_NAME, new DoubleWritable(currentRank));
				}
			}
		}
	}
}
